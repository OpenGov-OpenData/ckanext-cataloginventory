import logging
from datetime import datetime

import ckanapi
import ckan.model as model   # pylint: disable=R0402
import ckan.plugins as p

from ckan.common import config
from ckanext.cataloginventory.helpers import get_export_map_json


log = logging.getLogger(__name__)


# Get Dataset Catalog package_id and resource description from ini file
CATALOG_PACKAGE_ID = config.get('ckanext.cataloginventory.package_id', 'dataset-catalog')
CATALOG_RESOURCE_DESCRIPTION = config.get('ckanext.cataloginventory.resource_description', '')
MAP_FILENAME = config.get('ckanext.cataloginventory.map_filename', 'export.map.json')


def get_dataset_fields():
    """
    Get the dataset fields that will appear in the dataset catalog
    Custom schemas fields can be set to appear in the dataset catalog by setting MAP_FILENAME
    """
    dataset_fields = {}
    json_export_map = get_export_map_json(MAP_FILENAME)
    if not json_export_map:
        return None, None
    schema_fields = json_export_map.get('dataset_fields_map')
    ordered_fields = json_export_map.get('ordered_fields')

    for field_map in schema_fields:
        dataset_fields[field_map['field_name']] = field_map['label']

    dataset_fields['metadata_created'] = 'Created'
    dataset_fields['metadata_modified'] = 'Last Updated'
    dataset_fields['full_url'] = 'Dataset URL'
    dataset_fields['topic'] = 'Topic'
    return dataset_fields, ordered_fields


def get_record_data(pkg_dict, dataset_fields):
    """
    Build record data that will be sent to datastore API
    """
    if not pkg_dict.get('metadata_created'):
        local_ckan = ckanapi.LocalCKAN()  # running as site user
        full_pkg_dict = local_ckan.action.package_show(id=pkg_dict.get('id'))
        pkg_dict['metadata_created'] = full_pkg_dict['metadata_created']
        pkg_dict['metadata_modified'] = full_pkg_dict['metadata_modified']
        pkg_dict['groups'] = full_pkg_dict['groups']
        pkg_dict['organization'] = full_pkg_dict['organization']

    record_data = {}

    for key in dataset_fields:
        record_data[dataset_fields[key]] = ''
        if key in pkg_dict or key in ['tag_string', 'group', 'topic', 'full_url']:
            record_data[dataset_fields[key]] = ''
            if key == 'tag_string':
                if 'tag_string' in pkg_dict:
                    record_data[dataset_fields[key]] = pkg_dict.get('tag_string')
                else:
                    record_data[dataset_fields[key]] = get_package_tags(pkg_dict.get('tags', []))
            elif key in ['group', 'topic']:
                record_data[dataset_fields[key]] = get_package_groups(pkg_dict.get('groups', []))
            elif key in ['owner_org', 'organization'] and pkg_dict.get('organization'):
                record_data[dataset_fields[key]] = pkg_dict.get('organization', {}).get('title', '')
            elif key == 'full_url' and pkg_dict.get('name'):
                record_data[dataset_fields[key]] = '{0}/dataset/{1}'.format(
                    config.get('ckan.site_url'), pkg_dict.get('name', ''))
            else:
                record_data[dataset_fields[key]] = pkg_dict[key]
    return record_data


def get_package_groups(groups_dict):
    """
    Build out the group names comma separated string
    """
    groups = [group.get('display_name') for group in groups_dict if group.get('display_name')]
    return ','.join(groups)


def get_package_tags(tags_dict):
    """
    Build out the tag names comma separated string
    """
    tags = [tag.get('display_name') for tag in tags_dict if tag.get('display_name')]
    return ','.join(tags)


def get_all_packages():
    """
    Get all datasets when creating initial catalog resource
    """
    n = 500
    page = 1
    dataset_list = []

    while True:
        search_data_dict = {
            'q': '+capacity:public',
            'fq': 'dataset_type:dataset',
            'sort': 'title_string asc',
            'rows': n,
            'start': n * (page - 1),
        }

        query = p.toolkit.get_action('package_search')({}, search_data_dict)
        if len(query['results']):
            dataset_list.extend(query['results'])
            page += 1
        else:
            break

    return dataset_list


class CataloginventoryPlugin(p.SingletonPlugin):  # pylint: disable=W0612
    p.implements(p.IConfigurer)
    p.implements(p.IPackageController, inherit=True)

    class _InventoryChecks:
        @classmethod
        def skip_dataset_if_it_is_not_active(cls, plugin_method):
            def wrapper(plugin_ins, context, pkg_dict):
                if not pkg_dict.get('state', 'active') == 'active':
                    return
                plugin_method(plugin_ins, context, pkg_dict)

            return wrapper

        @classmethod
        def skip_dataset_if_it_is_private(cls, plugin_method):
            def wrapper(plugin_ins, context, pkg_dict):
                if pkg_dict.get('private', False):
                    return
                plugin_method(plugin_ins, context, pkg_dict)

            return wrapper

        @classmethod
        def skip_dataset_if_it_is_catalog(cls, plugin_method):
            def wrapper(plugin_ins, context, pkg_dict):
                if context.get('package') and context.get('package').name == CATALOG_PACKAGE_ID:
                    return
                if pkg_dict.get('name') == CATALOG_PACKAGE_ID:
                    return
                plugin_method(plugin_ins, context, pkg_dict)

            return wrapper

        @classmethod
        def skip_if_catalog_does_not_exist(cls, plugin_method):
            def wrapper(plugin_ins, context, pkg_dict):
                try:
                    local_ckan = ckanapi.LocalCKAN()  # running as site user
                    catalog_pkg_dict = local_ckan.action.package_show(id=CATALOG_PACKAGE_ID)
                    if catalog_pkg_dict.get('state') == 'deleted':
                        # user accidentally delete catalog
                        log.error('Catalog dataset is deleted, please create '
                                  'dataset with package_id: ' + CATALOG_PACKAGE_ID)
                        return
                except p.toolkit.ObjectNotFound:
                    # If catalog does not exist logs should not be spammed for every change
                    return
                else:
                    plugin_method(plugin_ins, context, pkg_dict)

            return wrapper

        @classmethod
        def skip_if_package_is_not_dataset(cls, plugin_method):
            def wrapper(plugin_ins, context, pkg_dict):
                if pkg_dict.get('type') != 'dataset':
                    return
                plugin_method(plugin_ins, context, pkg_dict)

            return wrapper

    # IConfigurer
    def update_config(self, config_):  # pylint: disable=R0201
        p.toolkit.add_template_directory(config_, 'templates')
        p.toolkit.add_public_directory(config_, 'public')
        p.toolkit.add_resource('fanstatic', 'cataloginventory')

    @_InventoryChecks.skip_dataset_if_it_is_not_active
    @_InventoryChecks.skip_dataset_if_it_is_private
    @_InventoryChecks.skip_dataset_if_it_is_catalog
    @_InventoryChecks.skip_if_catalog_does_not_exist
    @_InventoryChecks.skip_if_package_is_not_dataset
    def after_create(self, context, pkg_dict):  # pylint: disable=W0613
        self.upsert_catalog_inventory(pkg_dict)  # pylint: disable=W0613

    @_InventoryChecks.skip_dataset_if_it_is_not_active
    @_InventoryChecks.skip_dataset_if_it_is_catalog
    @_InventoryChecks.skip_if_catalog_does_not_exist
    @_InventoryChecks.skip_if_package_is_not_dataset
    def after_update(self, context, pkg_dict):  # pylint: disable=W0613
        if pkg_dict.get('private', True):  # pylint: disable=W0613
            self.delete_catalog_inventory_record(pkg_dict)
        else:
            self.upsert_catalog_inventory(pkg_dict)

    @_InventoryChecks.skip_dataset_if_it_is_catalog
    @_InventoryChecks.skip_dataset_if_it_is_not_active
    @_InventoryChecks.skip_dataset_if_it_is_private
    @_InventoryChecks.skip_if_catalog_does_not_exist
    def after_delete(self, context, pkg_dict):  # pylint: disable=W0613
        self.delete_catalog_inventory_record(pkg_dict)  # pylint: disable=W0613

    # Try to upsert dataset metadata
    # Resource with dataset catalog will be create if it doesn't exist
    def upsert_catalog_inventory(self, pkg_dict):
        local_ckan = ckanapi.LocalCKAN()  # running as site user
        catalog_pkg_dict = local_ckan.action.package_show(id=CATALOG_PACKAGE_ID)

        catalog_res_id = self.get_catalog_resource_id(catalog_pkg_dict)
        if not catalog_res_id:
            p.toolkit.enqueue_job(self.create_catalog_inventory, [catalog_pkg_dict])
            return

        dataset_fields, _ = get_dataset_fields()

        record_data = get_record_data(pkg_dict, dataset_fields)

        local_ckan.action.datastore_upsert(
            resource_id=catalog_res_id,
            records=[record_data]
        )

        self.update_last_modified_dates(catalog_res_id)

    # Create a new resource for dataset metadata
    def create_catalog_inventory(self, catalog_pkg_dict):
        local_ckan = ckanapi.LocalCKAN()  # running as site user
        dataset_fields, ordered_fields = get_dataset_fields()
        all_packages = get_all_packages()

        records = []
        for package in all_packages:
            if package.get('name') != CATALOG_PACKAGE_ID:
                record_data = get_record_data(package, dataset_fields)
                records.append(record_data)

        resource_dict = {
            'package_id': catalog_pkg_dict['name'],
            'name': 'Dataset Catalog',
            'description': CATALOG_RESOURCE_DESCRIPTION,
            'resource_type': 'csv',
            'last_modified': datetime.utcnow()
        }
        local_ckan.action.datastore_create(
            resource=resource_dict,
            fields=ordered_fields,
            records=records,
            primary_key=['Dataset ID']
        )

    # Delete the dataset record from the resource when it's deleted or made private
    def delete_catalog_inventory_record(self, pkg_dict):
        local_ckan = ckanapi.LocalCKAN()  # running as site user
        catalog_pkg_dict = local_ckan.action.package_show(id=CATALOG_PACKAGE_ID)

        catalog_res_id = self.get_catalog_resource_id(catalog_pkg_dict)
        if not catalog_res_id:
            p.toolkit.enqueue_job(self.create_catalog_inventory, [catalog_pkg_dict])
            return

        # Obtain slugified package name of dataset to delete from datastore table for Dataset Catalog
        delete_dataset_name = local_ckan.action.package_show(id=pkg_dict.get('id')).get('name')
        dataset_fields, _ = get_dataset_fields()

        # Delete row from resource 'Dataset Catalog' with the corresponding Dataset ID
        filters = {dataset_fields.get('name'): delete_dataset_name}
        local_ckan.action.datastore_delete(
            resource_id=catalog_res_id,
            filters=filters
        )

    @staticmethod
    def get_catalog_resource_id(pkg_dict):
        for resource_dict in pkg_dict['resources']:
            if resource_dict.get('name') == 'Dataset Catalog':
                return resource_dict['id']
        return ''

    @staticmethod
    def update_last_modified_dates(catalog_res_id):
        # Update last modified dates
        package = model.Package.get(CATALOG_PACKAGE_ID)
        resource = model.Resource.get(catalog_res_id)
        if package and resource:
            package.metadata_modified = datetime.utcnow()
            resource.last_modified = datetime.utcnow()
            package.save()
            resource.save()
