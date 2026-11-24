from docker.errors import DockerException

from . import RuntimeFailure


class ImageStorage:
    """Count shared layer chains once, falling back to full sizes if uncertain."""

    def __init__(self):
        self._cache = {}

    def _layers(self, image, size):
        layers = (image.attrs.get('RootFS') or {}).get('Layers')
        if not isinstance(layers, list) or not all(isinstance(layer, str) and layer for layer in layers):
            return None
        signature = (size, tuple(layers))
        cached = self._cache.get(image.id)
        if cached is not None and cached[0] == signature:
            return cached[1]
        try:
            history = image.history()
        except (DockerException, AttributeError):
            return None
        if not isinstance(history, list) or not all(
                isinstance(entry, dict) and type(entry.get('Size')) is int and entry['Size'] >= 0
                for entry in history):
            return None
        sizes = [entry['Size'] for entry in reversed(history) if entry['Size']]
        if len(sizes) != len(layers) or sum(sizes) != size:
            return None
        result = [(tuple(layers[:index + 1]), layer_size) for index, layer_size in enumerate(sizes)]
        self._cache[image.id] = (signature, result)
        return result

    def total(self, images):
        images = {image.id: image for image in images}
        self._cache = {identifier: entry for identifier, entry in self._cache.items() if identifier in images}
        shared = {}
        unverified = 0
        for image in images.values():
            size = image.attrs.get('Size')
            if type(size) is not int or size < 0:
                raise RuntimeFailure('Cannot verify Docker image storage size')
            layers = self._layers(image, size)
            if layers is None:
                unverified += size
                continue
            for chain, layer_size in layers:
                shared[chain] = max(shared.get(chain, 0), layer_size)
        return unverified + sum(shared.values())
