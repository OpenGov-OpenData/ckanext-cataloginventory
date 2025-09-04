"""Tests for plugin.py."""
import uuid
from datetime import datetime

import pytest
import ckan.plugins as p
from ckan.lib import search
from ckan.tests import helpers, factories

from ckanext.cataloginventory.plugin import CATALOG_PACKAGE_ID, CATALOG_RESOURCE_DESCRIPTION, get_record_data, \
    get_all_packages, get_dataset_fields


@pytest.fixture
def catalog_base_setup():
    """Fixture to set up the catalog base test environment."""
    # Create User with admin rights
    user = factories.Sysadmin(name='test-admin')
    org = factories.Organization(
        name='test-organisation',
        users=[{'name': user['name'], 'capacity': 'admin'}]
    )
    # Create Dataset Catalog Witch
    catalog_dataset = factories.Dataset(
        name=CATALOG_PACKAGE_ID,
        description=CATALOG_RESOURCE_DESCRIPTION,
        user=user,
        owner_org=org['id']
    )
    test_dataset = factories.Dataset(
        name='start-dataset',
        description='Dataset for init catalog res',
        user=user,
        owner_org=org['id']
    )
    catalog_id = catalog_dataset['id']
    catalog_res_id = create_catalog_inventory(user['name'])

    yield {
        'user': user,
        'org': org,
        'test_dataset': test_dataset,
        'catalog_id': catalog_id,
        'catalog_res_id': catalog_res_id
    }

    # Cleanup
    plugins = ['datastore', 'cataloginventory']
    for req_plugin in plugins:
        p.unload(req_plugin)
    helpers.reset_db()
    search.clear_all()


def create_catalog_inventory(user_name):
    """Create catalog inventory resource."""
    dataset_fields, ordered_fields = get_dataset_fields()
    records = []
    for package in get_all_packages():
        if package.get('name') != CATALOG_PACKAGE_ID:
            record_data = get_record_data(package, dataset_fields)
            records.append(record_data)
    resource = {
        'package_id': CATALOG_PACKAGE_ID,
        'name': 'Dataset Catalog',
        'description': CATALOG_RESOURCE_DESCRIPTION,
        'resource_type': 'csv',
        'last_modified': datetime.utcnow()
    }
    result = helpers.call_action('datastore_create',
                                 context={'user': user_name},
                                 resource=resource,
                                 fields=ordered_fields,
                                 records=records,
                                 primary_key=['Dataset ID'],
                                 )
    return result['resource_id']


def get_resource(res_id):
    """Get resource by ID."""
    return helpers.call_action(
        'datastore_search',
        resource_id=res_id
    )


def catalog_resource_contain_record_about_dataset(pck_data, catalog_res_id):
    """Check if catalog resource contains record about dataset."""
    catalog_res = helpers.call_action('datastore_search', resource_id=catalog_res_id)
    for record in catalog_res['records']:
        if record['Dataset ID'] == pck_data['id']:
            return True
    return False


def get_catalog(catalog_id):
    """Get catalog by ID."""
    return helpers.call_action('package_show', id=catalog_id)


def patch_dataset(dataset_data, user_name):
    """Patch dataset."""
    context = {
        'user': user_name
    }
    helpers.call_action('package_patch', context=context, **dataset_data)


def get_dataset_record_from_catalog(dataset_data, catalog_res_id):
    """Get dataset record from catalog."""
    res = get_resource(catalog_res_id)
    dataset_record = [r for r in res['records'] if r['Dataset ID'] == dataset_data['name']][0]
    return dataset_record


def generate_dataset_data(user, org_id, name=None, private=False, state='active', ptype='dataset'):
    """Generate dataset data for testing."""
    if name is None:
        name = str(uuid.uuid4())
    dataset_data = {
        'id': name,
        'name': name,
        'user': user,
        'owner_org': org_id,
        'private': private,
        'state': state,
        'type': ptype
    }
    return dataset_data


@pytest.mark.usefixtures('with_plugins', 'clean_db')
@pytest.mark.ckan_config('ckan.plugins', 'datastore cataloginventory')
class TestCatalogPackageDoesNotExist:
    """Test catalog package does not exist scenarios."""

    def test_after_create(self, catalog_base_setup, caplog):
        """Test after create when catalog package does not exist."""
        # Delete the catalog package but keep it with state='deleted' so logging works
        helpers.call_action('package_delete', id=catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)
        msg = 'Catalog dataset is deleted, please create dataset with package_id: ' + CATALOG_PACKAGE_ID
        assert msg in [record.message for record in caplog.records]

    def test_after_delete(self, catalog_base_setup, caplog):
        """Test after delete when catalog package does not exist."""
        # Delete the catalog package but keep it with state='deleted' so logging works
        helpers.call_action('package_delete', id=catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)
        helpers.call_action('package_delete', id=dataset_data['id'])
        msg = 'Catalog dataset is deleted, please create dataset with package_id: ' + CATALOG_PACKAGE_ID
        assert msg in [record.message for record in caplog.records]

    def test_after_update(self, catalog_base_setup, caplog):
        """Test after update when catalog package does not exist."""
        # Delete the catalog package but keep it with state='deleted' so logging works
        helpers.call_action('package_delete', id=catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)
        patch_dataset(dataset_data, catalog_base_setup['user']['name'])
        msg = 'Catalog dataset is deleted, please create dataset with package_id: ' + CATALOG_PACKAGE_ID
        assert msg in [record.message for record in caplog.records]


@pytest.mark.usefixtures('with_plugins', 'clean_db')
@pytest.mark.ckan_config('ckan.plugins', 'datastore cataloginventory')
class TestCatalogInventory:
    """Test catalog inventory functionality."""

    def test_after_create(self, catalog_base_setup):
        """Test after create dataset."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        # Dataset should not exist in res
        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        # Create dataset
        factories.Dataset(**dataset_data)
        # Record about new dataset should appear in catalog
        assert catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])

        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']

    def test_after_delete(self, catalog_base_setup):
        """Test after delete dataset."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)
        helpers.call_action('package_delete', id=dataset_data['id'])
        # Dataset should not exist in catalog
        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']

    def test_after_update_record_does_not_exist(self, catalog_base_setup):
        """Test after update when record does not exist."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)

        # Delete dataset record from catalog
        helpers.call_action(
            'datastore_delete',
            resource_id=catalog_base_setup['catalog_res_id'],
            filters={
                'Dataset ID': dataset_data['id']
            }
        )
        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        patch_dataset(dataset_data, catalog_base_setup['user']['name'])

        assert catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']

    def test_update_record_res_exist(self, catalog_base_setup):
        """Test update when record exists."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)
        # Remember field before patch
        last_update_before_patch = get_dataset_record_from_catalog(dataset_data, catalog_base_setup['catalog_res_id'])['Last Updated']

        patch_dataset(dataset_data, catalog_base_setup['user']['name'])
        # check that dataset record was updated in catalog
        assert last_update_before_patch != get_dataset_record_from_catalog(dataset_data, catalog_base_setup['catalog_res_id'])['Last Updated']
        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']

    def test_catalog_changes(self, catalog_base_setup):
        """Test that catalog should not react on changes made to Catalog."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        patch_dataset(catalog_data_dump, catalog_base_setup['user']['name'])
        catalog = get_catalog(catalog_base_setup['catalog_id'])
        assert not catalog_resource_contain_record_about_dataset(catalog, catalog_base_setup['catalog_res_id'])
        assert not (catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified'])


@pytest.mark.usefixtures('with_plugins', 'clean_db')
@pytest.mark.ckan_config('ckan.plugins', 'datastore cataloginventory')
class TestPrivateDataSets:
    """Test private datasets functionality.

    Catalog should not contain records about private dataset
    Catalog should contain datasets which is currently public
    """

    def test_after_create(self, catalog_base_setup):
        """Test after create private dataset."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id'],
            private=True
        )
        factories.Dataset(**dataset_data)

        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert not (catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified'])
        assert not (catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified'])

    def test_public_dataset_become_private(self, catalog_base_setup):
        """Test when public dataset becomes private."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id']
        )
        factories.Dataset(**dataset_data)

        dataset_data['private'] = True
        patch_dataset(dataset_data, catalog_base_setup['user']['name'])
        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']

    def test_private_dataset_become_public(self, catalog_base_setup):
        """Test when private dataset becomes public."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id'],
            private=True
        )
        factories.Dataset(**dataset_data)

        dataset_data['private'] = False
        patch_dataset(dataset_data, catalog_base_setup['user']['name'])

        assert catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']


@pytest.mark.usefixtures('with_plugins', 'clean_db')
@pytest.mark.ckan_config('ckan.plugins', 'datastore cataloginventory')
class TestDatasetState:
    """Test dataset state functionality."""

    def test_after_create(self, catalog_base_setup):
        """Test after create draft dataset."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id'],
            state='draft'
        )
        factories.Dataset(**dataset_data)

        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert not (catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified'])
        assert not (catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified'])

    def test_draft_dataset_become_active(self, catalog_base_setup):
        """Test when draft dataset becomes active."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id'],
            state='draft'
        )
        factories.Dataset(**dataset_data)

        dataset_data['state'] = 'active'
        patch_dataset(dataset_data, catalog_base_setup['user']['name'])
        assert catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified']
        assert catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified']


@pytest.mark.usefixtures('with_plugins', 'clean_db')
@pytest.mark.ckan_config('ckan.plugins', 'datastore cataloginventory')
class TestPackageWhichNotDatasetType:
    """Test packages which are not dataset type."""

    def test_after_create(self, catalog_base_setup):
        """Test after create non-dataset package."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id'],
            ptype='page'
        )
        factories.Dataset(**dataset_data)

        assert not catalog_resource_contain_record_about_dataset(dataset_data, catalog_base_setup['catalog_res_id'])
        assert not (catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified'])
        assert not (catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified'])

    def test_after_update(self, catalog_base_setup):
        """Test after update non-dataset package."""
        # Save catalog metadata before test runs
        catalog_data_dump = get_catalog(catalog_base_setup['catalog_id'])

        dataset_data = generate_dataset_data(
            catalog_base_setup['user'],
            catalog_base_setup['org']['id'],
            ptype='page'
        )
        factories.Dataset(**dataset_data)
        patch_dataset(dataset_data, catalog_base_setup['user']['name'])
        # Dataset should not exist in catalog
        assert not (catalog_data_dump['metadata_modified'] != get_catalog(catalog_base_setup['catalog_id'])['metadata_modified'])
        assert not (catalog_data_dump['resources'][0]['last_modified'] != get_catalog(catalog_base_setup['catalog_id'])['resources'][0]['last_modified'])
