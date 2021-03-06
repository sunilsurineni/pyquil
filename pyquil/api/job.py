##############################################################################
# Copyright 2016-2017 Rigetti Computing
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
##############################################################################

import base64
import warnings

from pyquil.api.errors import CancellationError, QVMError, QPUError
from pyquil.parser import parse_program
from pyquil.wavefunction import Wavefunction


class Job(object):
    """
    Represents the current status of a Job in the Forest queue.

    Job statuses are initially QUEUED when QVM/QPU resources are not available
    They transition to RUNNING when they have been started
    Finally they are marked as FINISHED, ERROR, or CANCELLED once completed
    """
    def __init__(self, raw, machine):
        self._raw = raw
        self._machine = machine

    @property
    def job_id(self):
        """
        Job id
        :rtype: str
        """
        return self._raw['jobId']

    def is_done(self):
        """
        Has the job completed yet?
        """
        return self._raw['status'] in ('FINISHED', 'ERROR', 'CANCELLED')

    def result(self):
        """
        The result of the job if available
        throws ValueError is result is not available yet
        throws ApiError if server returned an error indicating program execution was not successful
            or if the job was cancelled
        """
        if not self.is_done():
            raise ValueError("Cannot get a result for a program that isn't completed.")

        if self._raw['status'] == 'CANCELLED':
            raise CancellationError(self._raw['result'])
        elif self._raw['status'] == 'ERROR':
            if self._machine == 'QVM':
                raise QVMError(self._raw['result'])
            else:  # self._machine == 'QPU'
                raise QPUError(self._raw['result'])

        if self._raw['program']['type'] == 'wavefunction':
            return Wavefunction.from_bit_packed_string(
                base64.b64decode(self._raw['result']), self._raw['program']['addresses'])
        else:
            return self._raw['result']

    def is_queued(self):
        """
        Is the job still in the Forest queue?
        """
        return self._raw['status'] == 'QUEUED'

    def is_running(self):
        """
        Is the job currently running?
        """
        return self._raw['status'] == 'RUNNING'

    def position_in_queue(self):
        """
        If the job is queued, this will return how many other jobs are ahead of it.
        If the job is not queued, this will return None
        """
        if self.is_queued():
            return int(self._raw['position_in_queue'])

    def get(self):
        warnings.warn("""
        Running get() on a Job is now a no-op.
        To query for updated results, use .get_job(job.job_id) on a QVMConnection/QPUConnection instead
        """, stacklevel=2)

    def decode(self):
        warnings.warn(""".decode() on a Job result is deprecated in favor of .result()""", stacklevel=2)
        return self.result()

    def _get_metadata(self, key):
        """
        If the server returned a metadata dictionary, retrieve a particular key from it. If no
        metadata exists, or the key does not exist, return None.

        :param key: Metadata key, e.g., "gate_depth"
        :return: The associated metadata.
        :rtype: Optional[Any]
        """
        if not self.is_done():
            raise ValueError("Cannot get metadata for a program that isn't completed.")

        return self._raw.get("metadata", {}).get(key, None)

    def gate_depth(self):
        """
        If the job has metadata and this contains the gate depth, return this, otherwise None.
        The gate depth is a measure of how long a quantum program takes. On a non-fault-tolerant
        QPU programs with a low gate depth have a higher chance of succeeding.

        :rtype: Optional[int]
        """
        return self._get_metadata("gate_depth")

    def compiled_quil(self):
        """
        If the Quil program associated with the Job was compiled (e.g., to translate it to the
        QPU's natural gateset) return this compiled program.

        :rtype: Optional[Program]
        """
        prog = self._get_metadata("compiled_quil")
        if prog is not None:
            return parse_program(prog)

    def topological_swaps(self):
        """
        If the program could not be mapped directly to the QPU because of missing links in the
        two-qubit gate connectivity graph, the compiler must insert topological swap gates.
        Return the number of such topological swaps.

        :rtype: Optional[int]
        """
        return self._get_metadata("topological_swaps")
