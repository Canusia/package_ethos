from setuptools import setup, find_packages

setup(
    name='ethos',
    version='2026.8.0',
    description='Ellucian Ethos SIS integration client for MyCE',
    author='Canusia',
    packages=find_packages(exclude=['tests*', 'ethos_sis.tests*']),
    include_package_data=True,
    package_data={
        'ethos': [
            'templates/**/*',
            'staticfiles/**/*',
            'tests/fixtures/*.json',
        ],
    },
    install_requires=[
        'Django>=3.2',
        'requests>=2.31',
        'PyJWT>=2.0',
        'myce_cis>=0.1.5a',
    ],
    extras_require={
        'cli': ['python-dotenv>=1.0'],
    },
    entry_points={
        'console_scripts': [
            'ethos-sis = ethos_sis.cli:main',
        ],
    },
)
