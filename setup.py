from setuptools import find_packages, setup

setup(
    name="openimis-be-mapping",
    version="0.1.0",
    description="Configurable mapping APIs and host integrations for openIMIS and CoreMIS",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["Django>=4.2,<5", "graphene-django>=2,<3", "requests>=2.28,<3",
                      "openimis-be-core", "openimis-be-location"],
    license="AGPL-3.0-only",
    url="https://github.com/nlgfc2024/openimis-be-mapping_py",
)
