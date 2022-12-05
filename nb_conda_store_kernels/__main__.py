# https://github.com/Anaconda-Platform/nb_conda_kernels/blame/master/nb_conda_kernels/__main__.py
# Inspired by nb_conda_kernels to share configuration

from jupyter_client import kernelspec
from .manager import CondaStoreKernelSpecManager
kernelspec.KernelSpecManager = CondaStoreKernelSpecManager

from jupyter_client.kernelspecapp import KernelSpecApp

KernelSpecApp.launch_instance()
