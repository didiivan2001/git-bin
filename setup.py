from setuptools import setup


setup(
    name='git-bin',
    version='0.3.1',
    description='git extension to support binary files',
    author='srubenst',
    author_email='srubenst@cisco.com',
    license='MIT',
    keywords='binary git',
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
