from setuptools import setup, find_packages

version = '0.2.5'

setup(
    name='pyrcws',
    version=version,
    description="pyrcws",
    long_description="",
    classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords='redecard',
    author='Renato Pedigoni',
    author_email='renatopedigoni@gmail.com',
    url='http://github.com/rpedigoni/pyrcws',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=['suds'],
)
