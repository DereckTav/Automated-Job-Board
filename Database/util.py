from itertools import islice

def batch_zip(keys: list, *data: list):
    zipped = zip(*data)
    while True:
        chunk = list(islice(zipped, 3))
        if not chunk:
            break
        yield (dict(zip(keys, values)) for values in chunk)  # (data: dict, data: dict, data: dict)
