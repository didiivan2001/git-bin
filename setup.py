from setuptools import setup


setup(
    name='gitbin',
    version='0.3.0',
    description='git extension to support binary files',
    author='srubenst',
    author_email='srubenst@cisco.com',
    url='https://github.com/cisco-sas/git-bin',
    download_url='https://github.com/cisco-sas/git-bin',
    packages=["gitbin"],
    install_requires=['sh', 'docopt'],
    entry_points={
        'console_scripts': [
            'git-bin = gitbin.gitbin:main'
        ]
    },
)
