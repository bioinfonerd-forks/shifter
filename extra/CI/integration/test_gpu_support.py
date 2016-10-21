import unittest
import subprocess
import os
import sys
import re

_container_image=None

_gpu_libraries = [  "libcuda.so", \
                    "libnvcuvid.so", \
                    "libnvidia-compiler.so", \
                    "libnvidia-encode.so", \
                    "libnvidia-ml.so", \
                    "libnvidia-fatbinaryloader.so"]

class TestGPUDevices(unittest.TestCase):
    """
    These tests verify that the GPU resources and configurations (device files,
    libraries and value of LD_LIBRARY_PATH) are correctly set inside the container.
    """

    @classmethod
    def setUpClass(cls):
        #create GPU devices if necessary
        subprocess.call(["sudo", "touch", "/dev/nvidia0"])
        subprocess.call(["sudo", "touch", "/dev/nvidia1"])
        #create dummy GPU libraries
        path = os.path.dirname(os.path.abspath(__file__))
        subprocess.call(["mkdir", path+"/dummy-lib"])
        for gpu_lib in _gpu_libraries:
            subprocess.call(["cp", path+"/gpu_support_dummy_64bit_library.so", path+"/dummy-lib/"+gpu_lib])
        subprocess.call(["sudo", "ldconfig", path+"/dummy-lib"])

    @classmethod
    def tearDownClass(cls):
        path = os.path.dirname(os.path.abspath(__file__))
        subprocess.call(["sudo", "rm", "-rf", path+"/dummy-lib"])
        subprocess.call(["sudo", "ldconfig"])

    def setUp(self):
        self.cmdline_gpus=None
        self.environment_variable_gpus=None

    #no CUDA_VISIBLE_DEVICES + no --gpu option ==> container can see no GPU
    def test_no_environment_variable_and_no_command_line_option(self):
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, [])
        self.assertEqual(libs, [])

    #--gpu=0 ==> container can see /dev/nvidia0"
    def test_activate_gpu0_with_command_line_option(self):
        self.cmdline_gpus="0"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia0"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    #--gpu=1 ==> container can see /dev/nvidia1"
    def test_activate_gpu1_with_command_line_option(self):
        self.cmdline_gpus="1"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia1"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    #--gpu=0,1 ==> container can see both GPUs
    def test_activate_gpu0_and_gpu1_with_command_line_option(self):
        self.cmdline_gpus="0,1"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia0", "nvidia1"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    #CUDA_VISIBLE_DEVICES= ==> container can see no GPU
    def test_deactivate_gpus_with_environment_variablei_0(self):
        self.environment_variable_gpus=""
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, [])
        self.assertEqual(libs, [])
    
    #CUDA_VISIBLE_DEVICES=NoDevFiles ==> container can see no GPU
    def test_deactivate_gpus_with_environment_variable_1(self):
        self.environment_variable_gpus="NoDevFiles"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, [])
        self.assertEqual(libs, [])

    #CUDA_VISIBLE_DEVICES=0 ==> container can see /dev/nvidia0
    def test_activate_gpu0_with_environment_variable(self):
        self.environment_variable_gpus="0"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia0"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    #CUDA_VISIBLE_DEVICES=1 ==> container can see /dev/nvidia1
    def test_activate_gpu0_with_environment_variable(self):
        self.environment_variable_gpus="1"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia1"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    #CUDA_VISIBLE_DEVICES=0,1 ==> container can see both GPUs
    def test_activate_gpu0_and_gpu1_with_environment_variable(self):
        self.environment_variable_gpus="0,1"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia0", "nvidia1"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    #CUDA_VISIBLE_DEVICES= and --gpu=0,1 ==> container can see no GPU
    def test_environment_variable_overrides_command_line_option_0(self):
        self.cmdline_gpus="0,1"
        self.environment_variable_gpus=""
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, [])
        self.assertEqual(libs, [])
    
    #CUDA_VISIBLE_DEVICES=NoDevFiles and --gpu=0,1 ==> container can see no GPU
    def test_environment_variable_overrides_command_line_option_1(self):
        self.cmdline_gpus="0,1"
        self.environment_variable_gpus="NoDevFiles"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, [])
        self.assertEqual(libs, [])

    #CUDA_VISIBLE_DEVICES=0 and --gpu=0,1 ==> container can see /dev/nvidia0
    def test_environment_variable_overrides_command_line_option_2(self):
        self.cmdline_gpus="0,1"
        self.environment_variable_gpus="0"
        devices, libs = self._get_gpu_properties_in_container()
        self.assertEqual(devices, ["nvidia0"])
        self._assert_is_subset(subset=_gpu_libraries, superset=libs)

    def _get_gpu_properties_in_container(self):
        return (self._get_gpu_devices_in_container(), self._get_gpu_libraries_in_container() )

    def _get_gpu_devices_in_container(self):
        devices = self._get_command_output_in_container(["ls", "/dev"])
        expr = re.compile('nvidia[0-9]+')
        return [device for device in devices if expr.match(device) is not None]

    def _get_gpu_libraries_in_container(self):
        has_gpu_support = "gpu-support" in self._get_command_output_in_container(["ls", "/"])
        if has_gpu_support:
            return self._get_command_output_in_container(["ls", "/gpu-support/nvidia/lib64"])
        else:
            return []

    def _get_command_output_in_container(self, command):
        environment = os.environ.copy()
        if self.environment_variable_gpus is not None:
            environment["CUDA_VISIBLE_DEVICES"] = self.environment_variable_gpus

        full_command = ["shifter", "--image="+_container_image]
        if self.cmdline_gpus is not None:
            full_command += ["--gpu="+self.cmdline_gpus]
        full_command += command

        out = subprocess.check_output(full_command, env=environment)
        return [line for line in out.split('\n')]

    def _assert_is_subset(self, subset, superset):
        #dirty conversion to dictionaries required here
        #(there is no assertSetContainsSubset method)
        subset_dict = dict(zip(subset, len(subset)*[None]))
        superset_dict = dict(zip(superset, len(superset)*[None]))
        self.assertDictContainsSubset(subset_dict, superset_dict)

if __name__ == "__main__":
    _container_image=sys.argv[1]
    del sys.argv[1]
    unittest.main()
