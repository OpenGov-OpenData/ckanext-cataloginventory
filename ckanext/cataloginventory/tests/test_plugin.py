"""Tests for plugin.py."""
import uuid
from datetime import datetime

import ckan.plugins as p
from ckan.lib import search
from ckan.tests import helpers, factories
from nose.tools import assert_false, assert_true, assert_not_equal, assert_in
from testfixtures import LogCapture

from ckanext.cataloginventory.plugin import CATALOG_PACKAGE_ID, CATALOG_RESOURCE_DESCRIPTION, get_record_data, \
    get_all_packages, get_dataset_fields


class TestCatalogBase(object):
    plugins = ['datastore', 'cataloginventory']

    @classmethod
    def setup_class(cls):
        for req_plugin in cls.plugins:
            if not p.plugin_loaded(req_plugin):
                p.load(req_plugin)
        helpers.reset_db()
        search.clear_all()
        # Create User with admin rights
        cls.user = factories.Sysadmin(name='test-admin')
        cls.org = factories.Organization(
            name='test-organisation',
            users=[{'name': cls.user['name'], 'capacity': 'admin'}]
        )
        # Create Dataset Catalog Witch
        factories.Dataset(
            id=CATALOG_PACKAGE_ID,
            name=CATALOG_PACKAGE_ID,
            description=CATALOG_RESOURCE_DESCRIPTION,
            user=cls.user,
            owner_org=cls.org['id']
        )
        cls.test_dataset = factories.Dataset(
            id='start-dataset',
            name='start-dataset',
            description='Dataset for init catalog res',
            user=cls.user,
            owner_org=cls.org['id']
        )
        cls.catalog_id = CATALOG_PACKAGE_ID
        cls.catalog_res_id = cls.create_catalog_inventory(cls.user['name'])

    @classmethod
    def teardown_class(cls):
        for req_plugin in cls.plugins:
            p.unload(req_plugin)
        helpers.reset_db()
        search.clear_all()

    def catalog_resource_contain_record_about_dataset(self, pck_data):
        catalog_res = helpers.call_action('datastore_search', resource_id=self.catalog_res_id)
        for record in catalog_res['records']:
            if record['Dataset ID'] == pck_data['id']:
                return True
        return False

    def get_catalog(self):
        return helpers.call_action('package_show', id=self.catalog_id)

    @staticmethod
    def create_catalog_inventory(user_name):
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

    @staticmethod
    def get_resource(res_id):
        return helpers.call_action(
            'datastore_search',
            resource_id=res_id
        )

    def patch_dataset(self, dataset_data):
        context = {
            'user': self.user['name']
        }
        helpers.call_action('package_patch', context=context, **dataset_data)

    def get_dataset_record_from_catalog(self, dataset_data):
        res = self.get_resource(self.catalog_res_id)
        dataset_record = [r for r in res['records'] if r['Dataset ID'] == dataset_data['name']][0]
        return dataset_record

    def generate_dataset_data(self, name=None, private=False, state='active', ptype='dataset'):
        if name is None:
            name = str(uuid.uuid4())
        dataset_data = {
            'id': name,
            'name': name,
            'user': self.user,
            'owner_org': self.org['id'],
            'private': private,
            'state': state,
            'type': ptype
        }
        return dataset_data

    def catalog_resource_last_modified_changed(self):
        res_dump = self.catalog_data_dump['resources'][0]
        res_fresh = self.get_catalog()['resources'][0]
        return res_dump['last_modified'] != res_fresh['last_modified']

    def catalog_last_modified_changed(self):
        return self.catalog_data_dump['metadata_modified'] != self.get_catalog()['metadata_modified']

    def setup(self):
        # Save catalog metadata before tests runs
        self.catalog_data_dump = self.get_catalog()  # pylint: disable=W0201


# todo Create Test it after refactor workers call
# class TestCatalogInventoryResourceNotExist(TestCatalogBase):
#
#     def test_catalog_resource_does_not_exist(self):
#
#         # check that catalog resource doesnot exist
#         catalog = helpers.call_action('package_show', id=CATALOG_PACKAGE_ID)
#         assert len(catalog['resources']), 0
#         # create new dataset
#
#         dataset = factories.Dataset(
#             owner_org=self.org['id'],
#             name='den-dataset'
#         )
#         # check that resource was created
#         catalog = helpers.call_action('package_show', id=CATALOG_PACKAGE_ID)
#         pprint(catalog)
#         assert len(catalog['resources']), 1
#
#         # check that resource contain newly created dataset
#         assert True, self.check_catalog_res_contain_dataset(dataset)

class TestCatalogPackageDoesNotExist(TestCatalogBase):  # pylint: disable=W0612

    @classmethod
    def setup_class(cls):
        super(TestCatalogPackageDoesNotExist, cls).setup_class()
        helpers.call_action('package_delete', id=cls.catalog_id)

    def test_after_create(self):
        dataset_data = self.generate_dataset_data()
        with LogCapture() as logs:
            factories.Dataset(**dataset_data)
            msg = 'Catalog dataset is deleted, please create dataset with package_id: ' + CATALOG_PACKAGE_ID
            assert_in(msg, [log.msg for log in logs.records])

    def test_after_delete(self):
        dataset_data = self.generate_dataset_data()
        factories.Dataset(**dataset_data)
        with LogCapture() as logs:
            helpers.call_action('package_delete', id=dataset_data['id'])
            msg = 'Catalog dataset is deleted, please create dataset with package_id: ' + CATALOG_PACKAGE_ID
            assert_in(msg, [log.msg for log in logs.records])

    def test_after_update(self):
        dataset_data = self.generate_dataset_data()
        factories.Dataset(**dataset_data)
        with LogCapture() as logs:
            self.patch_dataset(dataset_data)
            msg = 'Catalog dataset is deleted, please create dataset with package_id: ' + CATALOG_PACKAGE_ID
            assert_in(msg, [log.msg for log in logs.records])


class TestCatalogInventory(TestCatalogBase):  # pylint: disable=W0612

    def test_after_create(self):
        dataset_data = self.generate_dataset_data()
        # Dataset should not exist in res
        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        # Create dataset
        factories.Dataset(**dataset_data)
        # Record about new dataset should appear in catalog
        assert_true(self.catalog_resource_contain_record_about_dataset(dataset_data))

        assert_true(self.catalog_last_modified_changed())
        assert_true(self.catalog_resource_last_modified_changed())

    def test_after_delete(self):
        dataset_data = self.generate_dataset_data()
        factories.Dataset(**dataset_data)
        helpers.call_action('package_delete', id=dataset_data['id'])
        # Dataset should not exist in catalog
        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_true(self.catalog_last_modified_changed())
        assert_true(self.catalog_resource_last_modified_changed())

    def test_after_update_record_does_not_exist(self):
        dataset_data = self.generate_dataset_data()
        factories.Dataset(**dataset_data)

        # Delete dataset record from catalog
        helpers.call_action(
            'datastore_delete',
            resource_id=self.catalog_res_id,
            filters={
                'Dataset ID': dataset_data['id']
            }
        )
        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        self.patch_dataset(dataset_data)

        assert_true(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_true(self.catalog_last_modified_changed())
        assert_true(self.catalog_resource_last_modified_changed())

    def test_update_record_res_exist(self):
        dataset_data = self.generate_dataset_data()
        factories.Dataset(**dataset_data)
        # Remember field before patch
        last_update_before_patch = self.get_dataset_record_from_catalog(dataset_data)['Last Updated']

        self.patch_dataset(dataset_data)
        # check that dataset record was updated in catalog
        assert_not_equal(last_update_before_patch, self.get_dataset_record_from_catalog(dataset_data)['Last Updated'])
        assert_true(self.catalog_last_modified_changed())
        assert_true(self.catalog_resource_last_modified_changed())

    def test_catalog_changes(self):
        """
        Catalog should not react on changes maked to Catalog
        """
        self.patch_dataset(self.catalog_data_dump)
        catalog = self.get_catalog()
        assert_false(self.catalog_resource_last_modified_changed())
        assert_false(self.catalog_resource_contain_record_about_dataset(catalog))


class TestPrivateDataSets(TestCatalogBase):  # pylint: disable=W0612
    """
    Catalog should not contain records about private dataset
    Catalog should contain datasets which is currently public
    """

    def test_after_create(self):
        dataset_data = self.generate_dataset_data(private=True)
        factories.Dataset(**dataset_data)

        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_false(self.catalog_resource_last_modified_changed())
        assert_false(self.catalog_last_modified_changed())

    def test_public_dataset_become_private(self):
        dataset_data = self.generate_dataset_data()
        factories.Dataset(**dataset_data)

        dataset_data['private'] = True
        self.patch_dataset(dataset_data)
        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_true(self.catalog_resource_last_modified_changed())
        assert_true(self.catalog_last_modified_changed())

    def test_private_dataset_become_public(self):
        dataset_data = self.generate_dataset_data(private=True)
        factories.Dataset(**dataset_data)

        dataset_data['private'] = False
        self.patch_dataset(dataset_data)

        assert_true(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_true(self.catalog_resource_last_modified_changed())
        assert_true(self.catalog_last_modified_changed())


class TestDatasetState(TestCatalogBase):  # pylint: disable=W0612

    def test_after_create(self):
        dataset_data = self.generate_dataset_data(state='draft')
        factories.Dataset(**dataset_data)

        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_false(self.catalog_resource_last_modified_changed())
        assert_false(self.catalog_last_modified_changed())

    def test_draft_dataset_become_active(self):
        dataset_data = self.generate_dataset_data(state='draft')
        factories.Dataset(**dataset_data)

        dataset_data['state'] = 'active'
        self.patch_dataset(dataset_data)
        assert_true(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_true(self.catalog_resource_last_modified_changed())
        assert_true(self.catalog_last_modified_changed())


class TestPackageWhichNotDatasetType(TestCatalogBase):  # pylint: disable=W0612
    def test_after_create(self):
        dataset_data = self.generate_dataset_data(ptype='page')
        factories.Dataset(**dataset_data)

        assert_false(self.catalog_resource_contain_record_about_dataset(dataset_data))
        assert_false(self.catalog_resource_last_modified_changed())
        assert_false(self.catalog_last_modified_changed())

    def test_after_update(self):
        dataset_data = self.generate_dataset_data(ptype='page')
        factories.Dataset(**dataset_data)
        self.patch_dataset(dataset_data)
        # Dataset should not exist in catalog
        assert_false(self.catalog_last_modified_changed())
        assert_false(self.catalog_resource_last_modified_changed())
