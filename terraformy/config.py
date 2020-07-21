import json
import pathlib
from typing import Iterable
from terraformpy import compile
from pydantic import BaseModel
import abc

import yaml

from .utils import exec
from .terrafile import Terrafile

class TerraformConfig(abc.ABC):
    name: str
    @abc.abstractmethod
    def config(self):
        pass

    @abc.abstractmethod
    def dict(self):
        pass

class BaseConfig(BaseModel, TerraformConfig):
    terrafile: Terrafile

    def module(self, name):
        dir = name

        if name in self.terrafile.entries and self.terrafile.entries[name].name:
            dir = self.terrafile.entries[name].name

        return "../../modules/{}".format(dir)

    class Config:
        arbitrary_types_allowed = True


class RootModule:
    name: str
    state_dir: str
    terrafile: Terrafile
    config: Iterable[TerraformConfig]

    def __init__(self, name: str, terrafile: Terrafile, config: Iterable[TerraformConfig]):
        self.name = name
        self.config = config
        self.terrafile = terrafile
        self.state_dir = "./state/{}".format(name)

    def insure_dir_exists(self):
        pathlib.Path(self.state_dir).mkdir(parents=True, exist_ok=True)

    def generate_config(self):
        self.insure_dir_exists()
        for conf in self.config:
            conf.config()
            with open("{}/{}.yaml".format(self.state_dir, conf.name), 'w') as file:
                yaml.dump(conf.dict(), file)

        print("terraformpy - Writing main.tf.json")

        with open("{}/main.tf.json".format(self.state_dir), "w") as fd:
            json.dump(compile(), fd, indent=4, sort_keys=True)

    def init(self, **kwargs):
        self.insure_dir_exists()
        return exec('terraform', 'init', cwd=self.state_dir, **kwargs)

    def plan(self, **kwargs):
        self.insure_dir_exists()
        return exec('terraform', 'plan', '-out=plan.saved', cwd=self.state_dir, **kwargs)

    def apply(self, **kwargs):
        self.insure_dir_exists()
        return exec('terraform', 'apply', '-auto-approve', cwd=self.state_dir, **kwargs)

    def destroy(self, **kwargs):
        self.insure_dir_exists()
        return exec('terraform', 'destroy', '-auto-approve', cwd=self.state_dir, **kwargs)
