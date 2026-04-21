from setuptools import setup, find_packages

setup(
    name='ethos',
    version='2026.0.14',
    description='Ellucian Ethos SIS integration client for MyCE',
    author='Canusia',
    packages=find_packages(exclude=['tests*']),
    include_package_data=True,
    package_data={
        'ethos': [
            'templates/**/*',
            'staticfiles/**/*',
        ],
    },
    install_requires=[
        'Django>=3.2',
    ],
)
