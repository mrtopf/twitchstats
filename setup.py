from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='twitchstats',
      version=version,
      description="Twitch Statistics Tool",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Christian Scholz',
      author_email='mrtopf@gmail.com',
      url='',
      license='BSD',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        "requests",
        "pymongo",
      ],
      entry_points="""
      [console_scripts]
      collect = twitchstats.scripts:collect
      """,
      )
