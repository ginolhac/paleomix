#!/usr/bin/python
#
# Copyright (c) 2012 Mikkel Schubert <MSchubert@snm.ku.dk>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import os

from pypeline.node import CommandNode
from pypeline.atomiccmd import AtomicCmd
from pypeline.atomicparams import *
from pypeline.atomicset import ParallelCmds

from pypeline.nodes.bwa import _process_output, _get_max_threads


class Bowtie2IndexNode(CommandNode):
    @create_customizable_cli_parameters
    def customize(cls, input_file, prefix = None, dependencies = ()):
        params = AtomicParams(("bowtie2-build"))
        params.push_positional("%(IN_FILE)s")

        # Destination prefix, in temp folder
        params.set_parameter("%(TEMP_OUT_PREFIX)s")

        prefix = prefix if prefix else input_file
        params.set_paths(IN_FILE = input_file,
                         TEMP_OUT_PREFIX = os.path.basename(prefix),
                         **_prefix_files(prefix, iotype = "OUT"))

        return {"prefix":  prefix,
                "command": params}


    @use_customizable_cli_parameters
    def __init__(self, parameters):
        command = parameters.command.finalize()
        description =  "<Bowtie2 Index '%s' -> '%s.*'>" % (parameters.input_file,
                                                       parameters.prefix)
        CommandNode.__init__(self,
                             command      = command,
                             description  = description,
                             dependencies = parameters.dependencies)



class Bowtie2Node(CommandNode):
    @create_customizable_cli_parameters
    def customize(cls, input_file_1, input_file_2, output_file, reference, prefix, threads = 2, dependencies = ()):
        aln = AtomicParams(("bowtie2",))
        aln.set_parameter("-x", prefix)

        if input_file_1 and not input_file_2:
            aln.set_parameter("-U", "%(IN_FILE_1)s")
        elif input_file_1 and input_file_2:
            aln.set_parameter("-1", "%(IN_FILE_1)s")
            aln.set_parameter("-2", "%(IN_FILE_2)s")
        else:
            raise NodeError("Input 1, OR both input 1 and input 2 must be specified for Bowtie2 node")

        max_threads = _get_max_threads(reference, threads)
        aln.set_parameter("--threads", max_threads)

        aln.set_paths(IN_FILE_1  = input_file_1,
                      IN_FILE_2  = input_file_2,
                      OUT_STDOUT = AtomicCmd.PIPE,
                      **_prefix_files(prefix))

        order, commands = _process_output(aln, output_file, reference)
        commands["aln"] = aln

        return {"commands" : commands,
                "order"    : ["aln"] + order,
                "threads"  : max_threads}


    @use_customizable_cli_parameters
    def __init__(self, parameters):
        command = ParallelCmds([parameters.commands[key].finalize() for key in parameters.order])

        aln_type    = "PE" if parameters.input_file_2 else "SE"
        description = "<Bowtie2 (%s, %i threads): '%s'>" \
          % (aln_type, parameters.threads, parameters.input_file_1)

        CommandNode.__init__(self,
                             command      = command,
                             description  = description,
                             threads      = parameters.threads,
                             dependencies = parameters.dependencies)





def _prefix_files(prefix, iotype = "IN"):
    files = {}
    for postfix in ("1.bt2", "2.bt2", "3.bt2", "4.bt2", "rev.1.bt2", "rev.2.bt2"):
        files["%s_PREFIX_%s" % (iotype, postfix.upper())] = prefix + "." + postfix
    return files