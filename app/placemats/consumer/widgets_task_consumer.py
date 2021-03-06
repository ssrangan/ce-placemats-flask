import app.placemats.data.ncbi_client as ncbi
from app.placemats.data.widget_spec_types import *
from app.placemats.consumer.consumer import BaseConsumer
from app.placemats.stores.task_queue_config import widgets_task_queue
from app.placemats.stores.store_config import widgets_store
from app.placemats.data.ncbi_client import *
from app.placemats.data.adjacency_matrix import *
from app.placemats.apis.layouts_api import STATUS_COMPLETE
from app.placemats.data.geo import *
import time
import logging

logger = logging.getLogger(__name__)


class WidgetsTaskConsumer(BaseConsumer):

    def __init__(self) -> None:
        super().__init__(widgets_task_queue())

    def consume_one(self, task_info: dict):
        spec_type = task_info['spec_type']
        data = None
        if spec_type == AUTHOR_ADJACENCY:
            data = self._author_adjacency(task_info)
        elif spec_type == AUTHOR_WORLD_MAP:
            data = self._author_world_map(task_info)
        if data is None:
            raise Exception('spec_type not recognized')
        else:
            logger.info('Created data for spec_type: %s', spec_type)
        self._update_store(task_info, data)

    def _author_adjacency(self, task_info: dict):
        term, = task_info['arguments']
        ai = author_info(term)
        a_to_pmids = ai.author_to_pmids
        top_n_authors = sorted(a_to_pmids.keys(), key=lambda a: len(a_to_pmids[a]), reverse=True)[:100]
        return adjacency_matrix(ai.pmid_to_authors, set(top_n_authors))

    def _author_world_map(self, task_info: dict):
        term, = task_info['arguments']
        af = affiliations(term)
        country_counts, code_to_country = get_country_counts(af.values())
        return [{
            'id': code_to_country[code].alpha3,
            'name': code_to_country[code].name,
            'articles': country_counts[code],
        } for code in country_counts]

    def _update_store(self, task_info, data):
        store = widgets_store()
        store.update(task_info['idempotency_key'], {'data': data, 'status': STATUS_COMPLETE})


def main():
    import os
    if os.environ.get('FLASK_ENV') == 'development':
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    from app.placemats.util import kwargs_from_environ
    ncbi.configure_client(**kwargs_from_environ({
        'NCBI_EMAIL': 'email',
        'NCBI_API_KEY': 'api_key',
    }))

    while True:
        try:
            WidgetsTaskConsumer().consume_forever()
        except KeyboardInterrupt:
            logger.info('Ctrl-C received. Exiting...')
            break
        except:
            logger.error('Error while running consumer forever. Sleeping and will try again.')
            time.sleep(10)
            continue


if __name__ == '__main__':
    main()
