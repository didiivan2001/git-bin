from setuptools import setup


setup(
    name='gitbin',
    version='0.2.0',
    description='git extension to support binary files',
    author='SAS team',
    author_email='stare-c-sas@cisco.com',
    url='https://git-sas.cisco.com/tools/gitbin.git',
    download_url='https://git-sas.cisco.com/tools/gitbin.git',
    packages=["gitbin"],
    install_requires=['sh', 'docopt'],
    entry_points={
        'console_scripts': [
            'git-bin = gitbin.gitbin:main'
        ]
    },
)
