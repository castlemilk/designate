# Copyright 2012 Managed I.T.
#
# Author: Kiall Mac Innes <kiall@managedit.ie>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from oslo_config import cfg
from oslo_log import log as logging
from IPy import IP
from designate.context import DesignateContext
from designate.objects import Record
from designate.notification_handler.base import NotificationHandler

LOG = logging.getLogger(__name__)

cfg.CONF.register_group(cfg.OptGroup(
    name='handler:filtered',
    title="Configuration for Nova Notification Handler"
))

cfg.CONF.register_opts([
    cfg.ListOpt('notification-topics', default=['notifications']),
    cfg.StrOpt('control-exchange', default='nova'),
    cfg.StrOpt('address-filter', default='*'),
    cfg.StrOpt('zone-id'),
    cfg.StrOpt('zone-name'),
    cfg.MultiStrOpt('formatv4'),
    cfg.MultiStrOpt('format', deprecated_for_removal=True,
                    deprecated_reason="Replaced by 'formatv4/formatv6'",
                    ),
    cfg.MultiStrOpt('formatv6')
], group='handler:filtered')


class FilteredHandler(NotificationHandler):
    """Handler for Nova's notifications"""
    __plugin_name__ = 'filtered'

    def get_exchange_topics(self):
        exchange = cfg.CONF[self.name].control_exchange

        topics = [topic for topic in cfg.CONF[self.name].notification_topics]

        return (exchange, topics)

    def get_event_types(self):
        return [
            'compute.instance.create.end',
            'compute.instance.delete.start',
        ]

    def process_notification(self, context, event_type, payload):
        LOG.debug('FilteredHandler received notification - %s', event_type)
        context = DesignateContext().elevated()
        context.all_tenants = True

        zone_id = cfg.CONF[self.name].zone_id
        zone_name = cfg.CONF[self.name].zone_name
        LOG.debug('FilteredHandler zone_id - %s', zone_id)
        LOG.debug('FilteredHandler zone_name - %s', zone_name)
        if event_type == 'compute.instance.create.end':
            valid_address = lambda x: IP(x) in IP(cfg.CONF[self.name].address_filter)
            payload['project'] = getattr(context, 'tenant', None)
            record_name = '%s.%s' % (payload['host'], zone_name)
            LOG.debug('FilteredHandler record_name - %s', record_name)
            filtered_addresses = []
            for address in payload['fixed_ips']:
                if valid_address(address['address']):
                    filtered_addresses.append(address)

            if filtered_addresses:
                LOG.debug('FilteredHandler Before Filtered %d', len(payload['fixed_ips']))
                LOG.debug('FilteredHandler After Filtered %d', len(filtered_addresses))
                for address in filtered_addresses:
                    recordset_values = {
                        'zone_id': zone_id,
                        'name': record_name,
                        'type': 'A' if address['version'] == 4 else 'AAAA'
                    }
                    record_values = {
                        'data': address['address'], 
                    }
                    LOG.debug('FilteredHandler:recordset_values:zone_id:', recordset_values['zone_id'])
                    LOG.debug('FilteredHandler:recordset_values:record_name:', recordset_values['name'])
                    LOG.debug('FilteredHandler:recordset_values:type:', recordset_values['type'])
                    LOG.debug('FilteredHandler:record_values:data:', record_values['data'])
                    recordset = self._find_or_create_recordset(context, **recordset_values)

                    LOG.debug('FilteredHandler:recordset:id:', recordset['id'])
                    self.central_api.create_record(context, zone_id, recordset['id'], Record(**record_values))
            else:
                LOG.debug('FilteredHandler No Results after filtering for %s', self.address_filter)

        elif event_type == 'compute.instance.delete.start':
            self._delete(zone_id=zone_id,
                         resource_id=payload['instance_id'],
                         resource_type='instance')
