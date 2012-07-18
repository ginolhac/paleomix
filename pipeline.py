import time
import signal
import multiprocessing

import ui
import taskgraph

from node import Node
from pylib.utilities import safe_coerce_to_tuple




class Pypeline:
    def __init__(self, config):
        self._nodes = []
        self._config = config


    def add_nodes(self, *nodes):
        for subnodes in safe_coerce_to_tuple(nodes):
            for node in safe_coerce_to_tuple(subnodes):
                if not isinstance(node, Node):
                    raise TypeError("Node object expected, recieved %s" % repr(node))
                self._nodes.append(node)


    def run(self, max_running = 4, dry_run = False):
        try:
            nodes = taskgraph.TaskGraph(self._nodes)
        except taskgraph.TaskError, error:
            ui.print_err(error)
            return False

        if dry_run:
            ui.print_node_tree(nodes)
            ui.print_msg("Dry run done ...")
            return 0
    
        try:
            running = {}
            pool = multiprocessing.Pool(max_running, _init_worker)
            while self._poll_running_nodes(running, nodes):
                if not self._start_new_tasks(running, nodes, max_running, pool):
                    ui.print_node_tree(nodes)
                    break

                ui.print_node_tree(nodes)

            pool.close()
            pool.join()

            if not self._poll_running_nodes(running, nodes):
                ui.print_err("Errors were detected ...")
                return False

        except taskgraph.TaskError, errors:
            ui.print_err("Error in task-graph, terminating gracefully:\n%s\n" \
                             % (node, "\n".join(("\t" + line) for line in str(errors).strip().split("\n"))))

            pool.terminate()
            pool.join()

        except KeyboardInterrupt:
            ui.print_err("Keyboard interrupt detected, terminating ...")
            pool.terminate()
            pool.join()

        ui.print_msg("Done ...")
        return True


    def _start_new_tasks(self, running, nodes, max_running, pool):
        any_runable_left = False
        idle_processes = max_running - len(running)
        for node in nodes.iterflat():
            any_runable_left |= (node.state in (node.RUNABLE, node.RUNNING))
            
            if idle_processes and (node.state == node.RUNABLE):
                running[node] = pool.apply_async(_call_run, args = (node.task, self._config))
                nodes.set_task_state(node, node.RUNNING)
                idle_processes -= 1
            
            if any_runable_left and not idle_processes:
                break

        return any_runable_left


    @classmethod
    def _poll_running_nodes(cls, running, nodes):
        changes = errors = False
        while running and not (errors or changes):
            time.sleep(1)

            for (node, proc) in running.items():
                if not proc.ready():
                    continue
                changes = True

                running.pop(node)
                nodes.set_task_state(node, None)
                   
                try:
                    proc.get()
                except Exception, errors:
                    nodes.set_task_state(node, node.ERROR)                    
                    ui.print_err("%s: Error occurred running command (terminating gracefully):\n%s\n" \
                                     % (node, "\n".join(("\t" + line) for line in str(errors).strip().split("\n"))))

        return not errors
 



def _init_worker():
    """Init function for subprocesses created by multiprocessing.Pool: Ensures that KeyboardInterrupts 
    only occur in the main process, allowing us to do proper cleanup."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _call_run(node, config):
    """Wrapper function, required in order to call Node.run()
    in subprocesses, since it is not possible to pickle 
    bound functions (e.g. self.run)"""
    return node.run(config)