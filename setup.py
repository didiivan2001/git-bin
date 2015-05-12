from setuptools import setup


setup(
    name='git-bin',
    version='0.3.0',
    description='git extension to support binary files',
    author='SAS team',
    author_email='stare-c-sas@cisco.com',
    url='https://offensive-git.cisco.com/sas-tools/git-bin.git',
    download_url='https://offensive-git.cisco.com/sas-tools/git-bin.git',
    packages=["git-bin"],
    install_requires=['sh', 'docopt'],
    entry_points={
        'console_scripts': [
            'git-bin = git-bin.git-bin:main'
        ]
    },
)
