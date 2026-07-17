from setuptools import setup
from setuptools_rust import Binding, RustBin

setup(
    rust_extensions=[
        RustBin("captivity-daemon", path="daemon-rs/Cargo.toml")
    ],
    # ensure zip_safe is False so the binary doesn't get buried in an egg
    zip_safe=False,
)
