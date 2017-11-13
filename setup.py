from setuptools import setup

setup(
  name = 'drf-related-views',
  packages = ['rest_framework_related'],
  version = '0.0.5',
  description = 'Related Views for Django Rest Framework',
  author = 'Fasih Ahmad Fakhri',
  author_email = 'fasihahmadfakhri@gmail.com',
  url = 'https://github.com/fasihahmad/django-rest-framework-related-views',
  download_url='https://github.com/fasihahmad/django-rest-framework-related-views/archive/v0.0.5.tar.gz',
  keywords = 'django rest framework related views',
  license='GPL-3.0',
  classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Framework :: Django',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries'
    ],
  install_requires=[
        'Django>=1.6.3',
        'django-filter>=0.11.0',
        'djangorestframework>=3.2.4',
        'djangorestframework-filters>=0.10.2'
    ],
)
