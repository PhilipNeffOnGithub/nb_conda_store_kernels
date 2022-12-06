import tempfile
import os

from jupyter_client.kernelspec import KernelSpecManager, KernelSpec, NoSuchKernel
# from jupyter_client.utils import run_sync
from traitlets import Bool, Unicode
from conda_store import api


class CondaStoreKernelSpecManager(KernelSpecManager):
    """A custom KernelSpecManager able to search conda-store for
    environments and create kernelspecs for them.
    """

    conda_store_url = Unicode(
        os.environ.get("CONDA_STORE_URL", "http://localhost:5000/"),
        help="Base prefix URL for connecting to conda-store cluster",
        config=True,
    )

    conda_store_verify_ssl = Bool(
        "CONDA_STORE_NO_VERIFY" not in os.environ,
        help="Verify all TLS connections",
        config=True,
    )

    conda_store_auth = Unicode(
        os.environ.get("CONDA_STORE_AUTH", "none"),
        help="Authentication type to use with Conda-Store. Available options are none, token, and basic",
        config=True,
    )

    name_format = Unicode(
        "{namespace}/{name}:{build}",
        config=True,
        help="""String name format; available field names within the string:
        '{namespace}' = Namespace for particular environment
        '{name}' = Environment name
        '{build}' = Build Id for particular environment
        """,
    )

    conda_store_only = Bool(
        False,
        config=True,
        help="Whether to include only the conda-store kernels not visible from Jupyter normally or not",
    )

    kernel_path = Unicode(
        "/usr/local/share/jupyter/kernels",
        config=True,
        help="Local path to kernelspecs"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.log.info("[nb_conda_store_kernels] enabled")

    @property
    def kernel_specs(self):
        return self._kernel_specs()
        # return run_sync(self._kernel_specs)()

    async def _kernel_specs(self):
        async with api.CondaStoreAPI(
            conda_store_url=self.conda_store_url,
            auth=self.conda_store_auth,
            verify_ssl=self.conda_store_verify_ssl,
        ) as conda_store_api:
            environments = await conda_store_api.list_environments(
                status="COMPLETED",
                artifact="CONDA_PACK",
                packages=["ipykernel"],
            )

        kernel_specs = {}
        for environment in environments:
            namespace = environment["namespace"]["name"]
            name = environment["name"]
            build = environment["current_build_id"]

            display_name = self.name_format.format(
                namespace=namespace, name=name, build=build
            )
            kernel_specs[f"conda-store://{namespace}/{name}:{build}"] = KernelSpec(
                display_name=display_name,
                argv=[
                    "conda-store",
                    "run",
                    str(build),
                    "--",
                    "python",
                    "-m",
                    "IPython",
                    "kernel",
                    "-f",
                    "{connection_file}",
                ],
                language="python",
                resource_dir=os.path.join(
                    tempfile.gettempdir(),
                    "conda-store",
                    str(build),
                ),
                metadata={},
            )

            self.log.info(f'Created spec for: {display_name}')
            kernel_spec_write = kernel_specs[f"conda-store://{namespace}/{name}:{build}"]
            kernel_name = self.clean_kernel_name(display_name)
            
            try:
                self.log.info(f'Install kernelspec locally')
                if not os.path.exists(f'{kernel_path}/{kernel_name}'):
                    self.log.debug(f'Creating directory {kernel_path}/{kernel_name} for new kernelspec')
                    os.makedirs(f'{kernel_path}/{kernel_name}')
                kernel_spec = join(f'{kernel_path}/{kernel_name}', "kernel.json")
                tmp_spec = kernel_spec_write.copy()
                
                self.log.info(f'Writing kernelspec to {kernel_spec} location')
                with open(kernel_spec, "w") as f:
                    json.dump(tmp_spec, f)
            except OSError as error:
                self.log.warning(
                    u"[nb_conda_kernels] Fail to install kernel",
                    exc_info=error
                )

        return kernel_specs

    def find_kernel_specs(self):
        if self.conda_store_only:
            kernel_specs = {}
        else:
            kernel_specs = super().find_kernel_specs()
        kernel_specs.update(
            {name: spec.resource_dir for name, spec in self.kernel_specs.items()}
        )
        return kernel_specs

    def get_kernel_spec(self, kernel_name):
        result = self.kernel_specs.get(kernel_name)
        if result is None and not self.conda_store_only:
            result = super().get_kernel_spec(kernel_name)
        return result

    def get_all_specs(self):
        result = {}
        for name, resource_dir in self.find_kernel_specs().items():
            try:
                spec = self.get_kernel_spec(name)
                result[name] = {"resource_dir": resource_dir, "spec": spec.to_dict()}
            except NoSuchKernel:
                self.log.warning("Error loading kernelspec %r", name, exc_info=True)
        return result

    def remove_kernel_spec(self, name):
        pass

    @staticmethod
    def clean_kernel_name(kname):
        """ Replaces invalid characters in the Jupyter kernelname, with
            a bit of effort to preserve readability.
        """
        try:
            kname.encode('ascii')
        except UnicodeEncodeError:
            # Replace accented characters with unaccented equivalents
            import unicodedata
            nfkd_form = unicodedata.normalize('NFKD', kname)
            kname = u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
        # Replace anything else, including spaces, with underscores
        kname = re.sub(r'[^a-zA-Z0-9._\-]', '_', kname)
        return kname   
