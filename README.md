## ckanext-cataloginventory
An extension to list datasets and their metadata in a resource labeled 'Dataset Catalog'.


## Requirements

**This plugin is compatible with CKAN 2.7 or later**

This plugin uses CKAN [background jobs](http://docs.ckan.org/en/latest/maintaining/background-tasks.html) that was introduced in CKAN 2.7

**This plugin can be made compatible with < 2.7 By installing rq extension**
[ckanext-rq](https://github.com/ckan/ckanext-rq.git)

## Installation

To install ckanext-cataloginventory, ensure you have installed ckanext-scheming:

1. Activate your CKAN virtual environment:
```
. /usr/lib/ckan/default/bin/activate
```

2. Download the extension's github repository:
```
cd /usr/lib/ckan/default/src
git clone https://github.com/OpenGov-OpenData/ckanext-cataloginventory.git
```

3. Install the extension into your virtual environment:
```
cd ckanext-cataloginventory
python setup.py develop
```

4. Add ``cataloginventory`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

5. Place the following configuration in your revelant .ini file below your plugin settings. This will enable the provided customizable default description for the dataset catalog resource.

```ini
ckanext.cataloginventory.resource_description = This dataset is a catalog of all the datasets available on the this data portal.
```
 PACKAGE_ID = config.get('ckanext.cataloginventory.package_id', 'dataset-catalog')

6. Configure which package id you want the resource 'Dataset Catalog' to appear in in your revelant .ini below , by default the package-id is "dataset-catalog". Add the following configuration in your revelant .ini file below your plugin settings to set the default package id.

```ini
ckanext.cataloginventory.package_id = dataset-catalog
```
Important: Verify that the dataset with the provided package id exists. For example, if using the default package id "dataset-catalog", make sure to create a dataset with that id if it does not currently exist so the "Dataset Catalog" resource may be generated within that dataset.

7. Add/Update an existing dataset and run the background job command to trigger adding of datasets to a resource under catalog-inventory


## Background Jobs
**Development**

Workers can be started using the [Run a background job worker](http://docs.ckan.org/en/latest/maintaining/paster.html#paster-jobs-worker) command:

For ckan 2.7
paster --plugin=ckan jobs worker --config=/etc/ckan/default/development.ini

For ckan 2.6 and lower
paster --plugin=ckanext-rq jobs worker --config=/etc/ckan/default/development.ini

**Production**

In a production setting, the worker should be run in a more robust way. One possibility is to use Supervisor.

For more information on setting up background jobs using Supervisor click [here](http://docs.ckan.org/en/latest/maintaining/background-tasks.html#using-supervisor).

