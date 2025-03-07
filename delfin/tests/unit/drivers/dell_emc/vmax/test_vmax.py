# Copyright 2020 The SODA Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from unittest import TestCase, mock

from requests.sessions import Session

from delfin import context
from delfin import exception
from delfin.common import constants, config  # noqa
from delfin.drivers.dell_emc.vmax.rest import VMaxRest
from delfin.drivers.dell_emc.vmax.vmax import VMAXStorageDriver


class Request:
    def __init__(self):
        self.environ = {'delfin.context': context.RequestContext()}
        pass


VMAX_STORAGE_CONF = {
    "storage_id": "12345",
    "vendor": "dell_emc",
    "model": "vmax",
    "rest": {
        "host": "10.0.0.1",
        "port": 8443,
        "username": "user",
        "password": "cGFzc3dvcmQ="
    },
    "extra_attributes": {
        "array_id": "00112233"
    }
}


class TestVMAXStorageDriver(TestCase):

    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_init(self, mock_unisphere_version,
                  mock_version, mock_array):
        kwargs = VMAX_STORAGE_CONF

        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.client.uni_version, '90')
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        with self.assertRaises(Exception) as exc:
            mock_version.side_effect = exception.InvalidIpOrPort
            VMAXStorageDriver(**kwargs)
        self.assertIn('Invalid ip or port', str(exc.exception))

        with self.assertRaises(Exception) as exc:
            mock_version.side_effect = exception.InvalidUsernameOrPassword
            VMAXStorageDriver(**kwargs)
        self.assertIn('Invalid username or password.', str(exc.exception))

    @mock.patch.object(VMaxRest, 'get_system_capacity')
    @mock.patch.object(VMaxRest, 'get_vmax_array_details')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_get_storage(self, mock_unisphere_version,
                         mock_version, mock_array,
                         mock_array_details, mock_capacity):
        expected = {
            'name': 'VMAX250F-00112233',
            'vendor': 'Dell EMC',
            'description': '',
            'model': 'VMAX250F',
            'firmware_version': '5978.221.221',
            'status': 'normal',
            'serial_number': '00112233',
            'location': '',
            'total_capacity': 109951162777600,
            'used_capacity': 82463372083200,
            'free_capacity': 27487790694400,
            'raw_capacity': 1610612736000,
            'subscribed_capacity': 219902325555200
        }
        system_capacity = {
            'system_capacity': {
                'usable_total_tb': 100,
                'usable_used_tb': 75,
                'subscribed_total_tb': 200
            },
            'physicalCapacity': {
                'total_capacity_gb': 1500

            }
        }
        system_capacity_84 = {
            'total_usable_cap_gb': 100 * 1024,
            'total_allocated_cap_gb': 75 * 1024,
            'total_subscribed_cap_gb': 200 * 1024,
            'physicalCapacity': {
                'total_capacity_gb': 1500
            }
        }
        kwargs = VMAX_STORAGE_CONF

        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}
        mock_array_details.return_value = {
            'model': 'VMAX250F',
            'ucode': '5978.221.221',
            'display_name': 'VMAX250F-00112233'}
        mock_capacity.return_value = system_capacity

        driver = VMAXStorageDriver(**kwargs)

        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        ret = driver.get_storage(context)
        self.assertDictEqual(ret, expected)

        driver.client.uni_version = '84'
        mock_capacity.return_value = system_capacity_84
        ret = driver.get_storage(context)
        self.assertDictEqual(ret, expected)

        mock_array_details.side_effect = exception.StorageBackendException
        with self.assertRaises(Exception) as exc:
            driver.get_storage(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

        mock_array_details.side_effect = [{
            'model': 'VMAX250F',
            'ucode': '5978.221.221',
            'display_name': 'VMAX250F-00112233'}]

        mock_capacity.side_effect = exception.StorageBackendException
        with self.assertRaises(Exception) as exc:
            driver.get_storage(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

    @mock.patch.object(VMaxRest, 'get_srp_by_name')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_list_storage_pools(self, mock_unisphere_version,
                                mock_version,
                                mock_array, mock_srp):
        expected = [{
            'name': 'SRP_1',
            'storage_id': '12345',
            'native_storage_pool_id': 'SRP_ID',
            'description': 'Dell EMC VMAX Pool',
            'status': 'normal',
            'storage_type': 'block',
            'total_capacity': 109951162777600,
            'used_capacity': 82463372083200,
            'free_capacity': 27487790694400,
            'subscribed_capacity': 219902325555200
        }]
        pool_info = {
            'srp_capacity': {
                'usable_total_tb': 100,
                'usable_used_tb': 75,
                'subscribed_total_tb': 200
            },
            'srpId': 'SRP_ID'
        }
        kwargs = VMAX_STORAGE_CONF
        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}
        mock_srp.side_effect = [{'srpId': ['SRP_1']}, pool_info]

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        ret = driver.list_storage_pools(context)
        self.assertDictEqual(ret[0], expected[0])

        mock_srp.side_effect = [{'srpId': ['SRP_1']},
                                exception.StorageBackendException]
        with self.assertRaises(Exception) as exc:
            driver.list_storage_pools(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

        mock_srp.side_effect = [exception.StorageBackendException, pool_info]
        with self.assertRaises(Exception) as exc:
            driver.list_storage_pools(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

    @mock.patch.object(VMaxRest, 'get_system_capacity')
    @mock.patch.object(VMaxRest, 'get_storage_group')
    @mock.patch.object(VMaxRest, 'get_volume')
    @mock.patch.object(VMaxRest, 'get_volume_list')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_list_volumes(self, mock_unisphere_version,
                          mock_version, mock_array,
                          mock_vols, mock_vol, mock_sg, mock_capacity):
        expected = \
            [
                {
                    'name': 'volume_1',
                    'storage_id': '12345',
                    'description': "Dell EMC VMAX 'thin device' volume",
                    'type': 'thin',
                    'status': 'available',
                    'native_volume_id': '00001',
                    'wwn': 'wwn123',
                    'total_capacity': 104857600,
                    'used_capacity': 10485760,
                    'free_capacity': 94371840,
                    'native_storage_pool_id': 'SRP_1',
                    'compressed': True
                },
                {
                    'name': 'volume_2:id',
                    'storage_id': '12345',
                    'description': "Dell EMC VMAX 'thin device' volume",
                    'type': 'thin',
                    'status': 'available',
                    'native_volume_id': '00002',
                    'wwn': 'wwn1234',
                    'total_capacity': 104857600,
                    'used_capacity': 10485760,
                    'free_capacity': 94371840,
                    'native_storage_pool_id': 'SRP_1'
                }
            ]
        volumes = {
            'volumeId': '00001',
            'cap_mb': 100,
            'allocated_percent': 10,
            'status': 'Ready',
            'type': 'TDEV',
            'wwn': 'wwn123',
            'num_of_storage_groups': 1,
            'storageGroupId': ['SG_001'],
            'emulation': 'FBA'
        }
        volumes1 = {
            'volumeId': '00002',
            'volume_identifier': 'id',
            'cap_mb': 100,
            'allocated_percent': 10,
            'status': 'Ready',
            'type': 'TDEV',
            'wwn': 'wwn1234',
            'num_of_storage_groups': 0,
            'storageGroupId': [],
            'emulation': 'FBA'
        }
        volumes2 = {
            'volumeId': '00003',
            'cap_mb': 100,
            'allocated_percent': 10,
            'status': 'Ready',
            'type': 'TDEV',
            'wwn': 'wwn1234',
            'num_of_storage_groups': 0,
            'storageGroupId': [],
            'emulation': 'CKD'
        }
        storage_group_info = {
            'srp': 'SRP_1',
            'compression': True
        }
        default_srps = {
            'default_fba_srp': 'SRP_1',
            'default_ckd_srp': 'SRP_2'
        }
        kwargs = VMAX_STORAGE_CONF
        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}
        mock_vols.side_effect = [['volume_1', 'volume_2', 'volume_3']]
        mock_vol.side_effect = [volumes, volumes1, volumes2]
        mock_sg.side_effect = [storage_group_info]
        mock_capacity.return_value = default_srps

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")
        ret = driver.list_volumes(context)
        self.assertDictEqual(ret[0], expected[0])
        self.assertDictEqual(ret[1], expected[1])

        mock_vols.side_effect = [['volume_1']]
        mock_vol.side_effect = [volumes]
        mock_sg.side_effect = [exception.StorageBackendException]
        with self.assertRaises(Exception) as exc:
            driver.list_volumes(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

        mock_vols.side_effect = [['volume_1']]
        mock_vol.side_effect = [exception.StorageBackendException]
        mock_sg.side_effect = [storage_group_info]
        with self.assertRaises(Exception) as exc:
            driver.list_volumes(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

        mock_vols.side_effect = [exception.StorageBackendException]
        mock_vol.side_effect = [volumes]
        mock_sg.side_effect = [storage_group_info]
        with self.assertRaises(Exception) as exc:
            driver.list_volumes(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

    @mock.patch.object(VMaxRest, 'get_resource')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_list_controllers(self, mock_unisphere_version,
                              mock_version,
                              mock_array, mock_res):
        expected = [
            {
                'name': 'DF-1C',
                'storage_id': '12345',
                'native_controller_id': 'DF-1C',
                'status': 'offline',
                'location': 'slot_10',
                'soft_version': None,
                'cpu_info': 'Cores-64',
                'memory_size': None
            }
        ]
        kwargs = VMAX_STORAGE_CONF
        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}
        mock_res.side_effect = [
            {'directorId': ['DF-1C', 'DF-2C']},
            {
                'availability': 'ON',
                'directorId': 'DF-1C',
                'director_number': 1,
                'director_slot_number': 10,
                'num_of_cores': 64,
                'num_of_ports': 2,
                'srdf_groups': [
                    {
                        'label': 'label_1',
                        'rdf_group_number': 1
                    }
                ]
            },
            {
                'availability': 'ON',
                'directorId': 'DF-2C',
                'director_number': 2,
                'director_slot_number': 10,
                'num_of_cores': 64,
                'num_of_ports': 2,
                'srdf_groups': [
                    {
                        'label': 'label_1',
                        'rdf_group_number': 1
                    }
                ]
            },
            {'directorId': ['DF-1C', 'DF-2C']},
            exception.StorageBackendException,
            exception.StorageBackendException
        ]

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        ret = driver.list_controllers(context)
        self.assertDictEqual(ret[0], expected[0])

        with self.assertRaises(Exception) as exc:
            driver.list_controllers(context)

        self.assertIn('Exception from Storage Backend',
                      str(exc.exception))

        with self.assertRaises(Exception) as exc:
            driver.list_controllers(context)

        self.assertIn('Exception from Storage Backend:',
                      str(exc.exception))

    @mock.patch.object(VMaxRest, 'get_resource_kwargs')
    @mock.patch.object(VMaxRest, 'get_director_list')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_list_ports(self, mock_unisphere_version,
                        mock_version,
                        mock_array, mock_dirs, mock_res):
        expected = [{
            'name': 'DF-1D:30',
            'storage_id': '12345',
            'native_port_id': '30',
            'location': 'director_DF-1D',
            'connection_status': 'connected',
            'health_status': 'normal',
            'type': 'other',
            'logical_type': 'backend',
            'speed': 0,
            'max_speed': 10737418240,
            'native_parent_id': 'DF-1D',
            'wwn': None,
            'mac_address': None,
            'ipv4': None,
            'ipv4_mask': None,
            'ipv6': None,
            'ipv6_mask': None
        }]
        kwargs = VMAX_STORAGE_CONF
        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}
        mock_dirs.return_value = ['DF-1C']
        mock_res.side_effect = [
            {
                'symmetrixPortKey': [
                    {
                        'directorId': 'DF-1D',
                        'portId': '30'
                    },
                    {
                        'directorId': 'DF-2C',
                        'portId': '0'
                    }
                ]
            },
            {
                'symmetrixPort': {
                    'aclx': False,
                    'avoid_reset_broadcast': False,
                    'common_serial_number': True,
                    'director_status': 'Offline',
                    'disable_q_reset_on_ua': False,
                    'enable_auto_negotiate': False,
                    'environ_set': False,
                    'hp_3000_mode': False,
                    'ip_addresses': [
                        '192.168.0.51'
                    ],
                    'iscsi_target': False,
                    'max_speed': '10',
                    'negotiate_reset': False,
                    'num_of_cores': 6,
                    'num_of_mapped_vols': 0,
                    'num_of_masking_views': 0,
                    'num_of_port_groups': 0,
                    'port_status': 'PendOn',
                    'scsi_3': False,
                    'scsi_support1': False,
                    'siemens': False,
                    'soft_reset': False,
                    'spc2_protocol_version': False,
                    'sunapee': False,
                    'symmetrixPortKey': {
                        'directorId': 'DF-1C',
                        'portId': '30'
                    },
                    'type': 'GigE',
                    'vnx_attached': False,
                    'volume_set_addressing': False
                }
            },
            {
                'symmetrixPort': {
                    'aclx': False,
                    'avoid_reset_broadcast': False,
                    'common_serial_number': True,
                    'director_status': 'Offline',
                    'disable_q_reset_on_ua': False,
                    'enable_auto_negotiate': False,
                    'environ_set': False,
                    'hp_3000_mode': False,
                    'ip_addresses': [
                        '192.168.0.51'
                    ],
                    'iscsi_target': False,
                    'max_speed': '10',
                    'negotiate_reset': False,
                    'num_of_cores': 6,
                    'num_of_mapped_vols': 0,
                    'num_of_masking_views': 0,
                    'num_of_port_groups': 0,
                    'port_status': 'PendOn',
                    'scsi_3': False,
                    'scsi_support1': False,
                    'siemens': False,
                    'soft_reset': False,
                    'spc2_protocol_version': False,
                    'sunapee': False,
                    'symmetrixPortKey': {
                        'directorId': 'DF-2C',
                        'portId': '0'
                    },
                    'type': 'GigE',
                    'vnx_attached': False,
                    'volume_set_addressing': False
                }
            },
            {
                'symmetrixPortKey': [
                    {
                        'directorId': 'DF-1C',
                        'portId': '30'
                    },
                    {
                        'directorId': 'DF-2C',
                        'portId': '0'
                    }
                ]
            },
            exception.StorageBackendException,
            exception.StorageBackendException
        ]

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        ret = driver.list_ports(context)
        self.assertDictEqual(ret[0], expected[0])

        mock_dirs.side_effect = exception.StorageBackendException
        with self.assertRaises(Exception) as exc:
            driver.list_ports(context)

        self.assertIn('Exception from Storage Backend:',
                      str(exc.exception))

        with self.assertRaises(Exception) as exc:
            driver.list_ports(context)

        self.assertIn('Exception from Storage Backend:',
                      str(exc.exception))

    @mock.patch.object(Session, 'request')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_rest(self, mock_unisphere_version,
                  mock_version, mock_array,
                  mock_request):
        kwargs = VMAX_STORAGE_CONF

        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.client.uni_version, '90')
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        mock_request.return_value = mock.Mock()
        mock_request.return_value.json = mock.Mock(return_value={})
        driver.reset_connection(context, **kwargs)
        driver.client.rest.session = None
        driver.client.rest.request('/session', 'GET')
        self.assertEqual(driver.client.uni_version, '90')

    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_get_capabilities(self, mock_unisphere_version,
                              mock_version, mock_array):
        kwargs = VMAX_STORAGE_CONF

        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}
        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.client.uni_version, '90')
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")

        capabilities = driver.get_capabilities(context)
        self.assertIsNotNone(capabilities)
        self.assertIsInstance(capabilities, dict)
        self.assertEqual(capabilities['is_historic'], True)
        self.assertIsInstance(capabilities['resource_metrics'], dict)
        # Support storage, storage_pool, controller and port metrics
        self.assertEqual(len(capabilities['resource_metrics']), 4)

    @mock.patch.object(VMaxRest, 'get_resource_metrics')
    @mock.patch.object(VMaxRest, 'get_resource_keys')
    @mock.patch.object(VMaxRest, 'get_array_keys')
    @mock.patch.object(VMaxRest, 'get_array_detail')
    @mock.patch.object(VMaxRest, 'get_uni_version')
    @mock.patch.object(VMaxRest, 'get_unisphere_version')
    def test_collect_perf_metrics(self, mock_unisphere_version,
                                  mock_version,
                                  mock_array, mock_array_keys,
                                  mock_r_keys, mock_r_metrics):
        expected = [
            constants.metric_struct(name='iops',
                                    labels={
                                        'storage_id': '12345',
                                        'resource_type': 'storage',
                                        'resource_id': '00112233',
                                        'resource_name': 'VMAX00112233',
                                        'type': 'RAW',
                                        'unit': 'IOPS'},
                                    values={1566550500000: 417.42667}
                                    ),
            constants.metric_struct(name='iops',
                                    labels={
                                        'storage_id': '12345',
                                        'resource_type': 'storagePool',
                                        'resource_id': 'SRP_1',
                                        'resource_name': 'SRP_1',
                                        'type': 'RAW',
                                        'unit': 'IOPS'},
                                    values={1566550800000: 304.8}
                                    ),
            constants.metric_struct(name='iops',
                                    labels={
                                        'storage_id': '12345',
                                        'resource_type': 'controller',
                                        'resource_id': 'DF-1C',
                                        'resource_name': 'BEDirector_DF-1C',
                                        'type': 'RAW',
                                        'unit': 'IOPS'
                                    },
                                    values={1566987000000: 248.40666}
                                    ),
            constants.metric_struct(name='iops',
                                    labels={
                                        'storage_id': '12345',
                                        'resource_type': 'port',
                                        'resource_id': '12',
                                        'resource_name': 'BEPort_DF-1C_12',
                                        'type': 'RAW',
                                        'unit': 'IOPS'
                                    },
                                    values={1566987000000: 6.693333}
                                    ),
        ]
        kwargs = VMAX_STORAGE_CONF
        mock_version.return_value = ['V9.0.2.7', '90']
        mock_unisphere_version.return_value = ['V9.0.2.7', '90']
        mock_array.return_value = {'symmetrixId': ['00112233']}

        driver = VMAXStorageDriver(**kwargs)
        self.assertEqual(driver.storage_id, "12345")
        self.assertEqual(driver.client.array_id, "00112233")
        ret_array_key = {
            "arrayInfo": [{
                "symmetrixId": "00112233",
                "firstAvailableDate": "1566146400000",
                "lastAvailableDate": "1566550800000",
            }]
        }
        ret_pool_key = {
            "srpInfo": [
                {
                    "srpId": "SRP_1",
                    "firstAvailableDate": 1567065600000,
                    "lastAvailableDate": 1568130900000
                },
            ]
        }
        ret_be_dir_key = {
            "beDirectorInfo": [
                {
                    "directorId": "DF-1C",
                    "firstAvailableDate": 1566557100000,
                    "lastAvailableDate": 1566987300000
                },
            ]
        }
        ret_fe_dir_key = {
            "feDirectorInfo": [
                {
                    "directorId": "FA-1D",
                    "firstAvailableDate": 1567065600000,
                    "lastAvailableDate": 1567093200000
                },
            ]
        }
        ret_rdf_dir_key = {
            "rdfDirectorInfo": [
                {
                    "directorId": "RF-1F",
                    "firstAvailableDate": 1567065600000,
                    "lastAvailableDate": 1567437900000
                },
            ]
        }
        ret_be_port_key = {
            "bePortInfo": [
                {
                    "portId": "12",
                    "firstAvailableDate": 1566557100000,
                    "lastAvailableDate": 1566988500000
                },
            ]
        }
        ret_fe_port_key = {
            "fePortInfo": [
                {
                    "firstAvailableDate": 1567065600000,
                    "lastAvailableDate": 1567162500000,
                    "portId": "4"
                },
            ]
        }
        ret_rdf_port_key = {
            "rdfPortInfo": [
                {
                    "portId": "7",
                    "firstAvailableDate": 1567065600000,
                    "lastAvailableDate": 1567439100000
                }
            ]
        }
        mock_array_keys.return_value = ret_array_key
        mock_r_keys.side_effect = [
            ret_pool_key,
            ret_be_dir_key, ret_fe_dir_key, ret_rdf_dir_key,
            ret_be_dir_key, ret_be_port_key,
            ret_fe_dir_key, ret_fe_port_key,
            ret_rdf_dir_key, ret_rdf_port_key,
        ]
        ret_array_metric = {
            "HostIOs": 417.42667,
            "HostMBs": 0.0018131511,
            "FEReqs": 23.55,
            "BEIOs": 25.216667,
            "BEReqs": 5.55,
            "PercentCacheWP": 0.031244868,
            "timestamp": 1566550500000
        }
        ret_pool_metric = {
            "HostIOs": 304.8,
            "HostMBs": 0.005192057,
            "FEReqs": 23.04,
            "BEIOs": 22.566668,
            "BEReqs": 4.7733335,
            "PercentCacheWP": 0.018810686,
            "timestamp": 1566550800000
        }
        ret_be_dir_metric = {
            "PercentBusy": 0.025403459,
            "IOs": 248.40666,
            "Reqs": 3.91,
            "MBRead": 1.7852213,
            "MBWritten": 0.37213543,
            "PercentNonIOBusy": 0.0,
            "timestamp": 1566987000000
        }
        ret_fe_dir_metric = {
            "PercentBusy": 2.54652,
            "HostIOs": 3436.9368,
            "HostMBs": 51.7072,
            "Reqs": 3330.5947,
            "ReadResponseTime": 0.12916493,
            "WriteResponseTime": 0.3310084,
            "timestamp": 1567078200000
        }
        ret_rdf_dir_metric = {
            "PercentBusy": 4.8083158,
            "IOs": 1474.2234,
            "WriteReqs": 1189.76,
            "MBWritten": 54.89597,
            "MBRead": 0.4565983,
            "MBSentAndReceived": 55.35257,
            "AvgIOServiceTime": 0.89211756,
            "CopyIOs": 0.0,
            "CopyMBs": 0.0,
            "timestamp": 1567161600000
        }
        ret_be_port_metric = {
            "Reads": 4.7,
            "Writes": 1.9933333,
            "IOs": 6.693333,
            "MBRead": 0.43401042,
            "MBWritten": 0.10486979,
            "MBs": 0.5388802,
            "AvgIOSize": 82.44224,
            "PercentBusy": 0.013356605,
            "timestamp": 1566987000000
        }
        ret_fe_port_metric = {
            "ResponseTime": 0.1263021,
            "ReadResponseTime": 0.1263021,
            "WriteResponseTime": 0.0,
            "Reads": 0.32,
            "Writes": 0.0,
            "IOs": 0.32,
            "MBRead": 4.296875E-4,
            "MBWritten": 0.0,
            "MBs": 4.296875E-4,
            "AvgIOSize": 1.375,
            "SpeedGBs": 16.0,
            "PercentBusy": 2.6226044E-5,
            "timestamp": 1567161600000
        }
        ret_rdf_port_metric = {
            "Reads": 0.0,
            "Writes": 1216.7633,
            "IOs": 1216.7633,
            "MBRead": 0.0,
            "MBWritten": 57.559597,
            "MBs": 57.559597,
            "AvgIOSize": 48.440834,
            "SpeedGBs": 16.0,
            "PercentBusy": 3.5131588,
            "timestamp": 1567161600000
        }
        mock_r_metrics.side_effect = [
            [ret_array_metric],
            [ret_pool_metric],
            [ret_be_dir_metric],
            [ret_fe_dir_metric],
            [ret_rdf_dir_metric],
            [ret_be_port_metric],
            [ret_fe_port_metric],
            [ret_rdf_port_metric],
        ]
        resource_metrics = {
            'storage': {'iops': {'unit': 'IOPS'}},
            'storagePool': {'iops': {'unit': 'IOPS'}},
            'controller': {'iops': {'unit': 'IOPS'}},
            'port': {'iops': {'unit': 'IOPS'}},
        }
        ret = driver.collect_perf_metrics(context,
                                          driver.storage_id,
                                          resource_metrics,
                                          1000, 2000)

        self.assertEqual(ret[0], expected[0])
        self.assertEqual(ret[2], expected[1])
        self.assertEqual(ret[4], expected[2])
        self.assertEqual(ret[13], expected[3])

        with self.assertRaises(Exception) as exc:
            driver.collect_perf_metrics(context,
                                        driver.storage_id,
                                        resource_metrics,
                                        1000, 2000
                                        )

        self.assertIn('', str(exc.exception))
