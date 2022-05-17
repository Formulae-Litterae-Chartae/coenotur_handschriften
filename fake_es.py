import os
import json

# Thanks to https://dev.to/jeffreymfarley/mocking-elasticsearch-5goj for this method of mocking ES


class FakeElasticsearch(object):
    def __init__(self,
                 short_name,
                 subdir,
                 endpoint='_search'):

        self.short_name = short_name
        self.path = os.path.join(
            os.path.dirname(__file__),
            "test_data",
            subdir,
            "__mocks__",
            endpoint
        )

    def build_path(self, suffix: str) -> str:
        return os.path.join(
            self.path, self.short_name + suffix
        )

    def load_request(self) -> dict:
        file_name = self.build_path('_req.json')
        with open(file_name, 'r') as f:
            return json.load(f)

    def load_response(self) -> dict:
        file_name = self.build_path('_resp.json')
        with open(file_name, 'r') as f:
            return json.load(f)

    def save_request(self, body: list):
        file_name = self.build_path('_req.json')
        with open(file_name, 'w') as f:
            json.dump(body, f, indent=2, ensure_ascii=False)

    def save_response(self, resp: list):
        file_name = self.build_path('_resp.json')
        with open(file_name, 'w') as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

    def save_ids(self, ids: list):
        file_name = self.build_path('_ids.json')
        with open(file_name, 'w') as f:
            json.dump(ids, f, indent=2, ensure_ascii=False)

    def load_ids(self) -> dict:
        file_name = self.build_path('_ids.json')
        with open(file_name, 'r') as f:
            return json.load(f)

    def save_aggs(self, aggs: dict):
        file_name = self.build_path('_aggs.json')
        with open(file_name, 'w') as f:
            json.dump({'aggregations': aggs}, f, indent=2, ensure_ascii=False)

    def load_aggs(self) -> dict:
        file_name = self.build_path('_aggs.json')
        with open(file_name, 'r') as f:
            return json.load(f)
