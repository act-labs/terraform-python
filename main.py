from terraformpy import Module, Provider

from terraformy.terrafile import Terrafile
from terraformy.config import BaseConfig, RootModule


class MyVpc(BaseConfig):
    name: str
    region: str = "eu-west-2"
    private_number: int = 2
    public_number: int = 2

    def config(self):
        name = self.name
        region = self.region
        private_number = self.private_number
        public_number = self.public_number

        Provider("aws", region=region)
        params = dict(
            source=self.module("aws-vps"),
            name=name,
            cidr="10.0.0.0/16",
            azs=[region + "a", region + "b"],
            private_subnets=[
                "10.0.{}.0/24".format(k) for k in range(1, private_number + 1)
            ],
            public_subnets=[
                "10.0.10{}.0/24".format(k) for k in range(1, public_number + 1)
            ],
            enable_ipv6="true",
            enable_nat_gateway="true",
            single_nat_gateway="true",
            public_subnet_tags={"Name": "overridden-name-public"},
            tags={"Owner": "user", "Environment": "dev"},
            vpc_tags={"Name": name},
        )

        Module(name, **params)


if __name__ == "__main__":
    terrafile = Terrafile()
    terrafile.update()

    root_module_name = "my-vpc"
    my_vpc = MyVpc(name=root_module_name, terrafile=terrafile)

    module = RootModule(root_module_name, terrafile=terrafile, config=[my_vpc])
    module.generate_config()
    module.init()
    module.apply()

