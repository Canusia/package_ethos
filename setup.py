from setuptools import setup, find_packages

setup(
    name='ethos',
    version='1.0.0',
    description='Ellucian Ethos SIS integration client for MyCE',
    author='Canusia',
    packages=find_packages(exclude=['tests*']),
    install_requires=[
        'Django>=3.2',
    ],
)
