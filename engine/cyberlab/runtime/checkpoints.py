import logging
from uuid import uuid4

from docker.errors import DockerException
from cyberlab.lab.workstation import validate_images

from . import RuntimeFailure
from .image_storage import ImageStorage

CHECKPOINT_LABEL = "org.ptit.cyberlab.checkpoint"
OWNER_LABEL = "org.ptit.cyberlab.checkpoint-owner"
NODE_LABEL = "org.ptit.cyberlab.checkpoint-node"
SESSION_LABEL = "org.ptit.cyberlab.checkpoint-session"
SCOPE_LABEL = "org.ptit.cyberlab.checkpoint-scope"
MAX_IMAGE_BYTES = 2 * 1024**3
MAX_CHECKPOINT_BYTES = 12 * 1024**3

class SystemCheckpoints:
    def __init__(self, runtime, scope="production"):
        self.runtime = runtime
        self.client = runtime.client
        self.scope = scope
        self.storage = ImageStorage()

    def restore_image(self, session, node, image_id):
        validate_images({node.id: image_id})
        try:
            image = self.client.images.get(image_id)
            labels = image.attrs.get("Config", {}).get("Labels") or {}
            expected = {CHECKPOINT_LABEL: "v1", OWNER_LABEL: str(session.owner_uid),
                        SESSION_LABEL: session.id, NODE_LABEL: node.id, SCOPE_LABEL: self.scope}
            if image.id != image_id or any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeFailure("Saved system image ownership does not match this Session")
            if image.attrs.get("Config", {}).get("Volumes"):
                raise RuntimeFailure("Saved system image must not declare host or anonymous volumes")
            return image.id
        except DockerException:
            raise RuntimeFailure("Saved Ubuntu system image is unavailable; checkpoint retained, do not reset") from None

    def capture(self, session):
        images = {}
        if not any(node.image in self.runtime.workstation_images for node in session.lab.nodes):
            return images
        try:
            known = self.client.images.list(filters={"label": [f"{CHECKPOINT_LABEL}=v1", f"{SCOPE_LABEL}={self.scope}"]})
            total = self.storage.total(known)
            for node in session.lab.nodes:
                if node.image not in self.runtime.workstation_images:
                    continue
                container = self.runtime._workspace_container(session, node)
                matches = self.client.api.containers(all=True, size=True, filters={"id": container.id})
                if len(matches) != 1 or matches[0].get("Id") != container.id:
                    raise RuntimeFailure("Cannot verify the Ubuntu container size before saving")
                size = matches[0].get("SizeRootFs")
                if not isinstance(size, int) or not 0 <= size <= MAX_IMAGE_BYTES or total + size > MAX_CHECKPOINT_BYTES:
                    raise RuntimeFailure("Ubuntu checkpoint storage limit reached (2 GiB/node, 12 GiB total); Session is still running")
                labels = {CHECKPOINT_LABEL: "v1", OWNER_LABEL: str(session.owner_uid),
                          SESSION_LABEL: session.id, NODE_LABEL: node.id, SCOPE_LABEL: self.scope}
                image = container.commit(repository="cyberlab-checkpoint", tag=uuid4().hex, pause=True,
                                         conf={"Labels": labels})
                images[node.id] = image.id
                total += size
            return images
        except Exception:
            self.release(images.values())
            raise

    def release(self, images):
        for image_id in dict.fromkeys(images):
            try:
                validate_images({"node": image_id})
                image = self.client.images.get(image_id)
                labels = image.attrs.get("Config", {}).get("Labels") or {}
                if labels.get(CHECKPOINT_LABEL) == "v1" and labels.get(SCOPE_LABEL) == self.scope:
                    self.client.images.remove(image_id, force=False, noprune=True)
            except (DockerException, ValueError):
                logging.warning("Unused system checkpoint retained; retry cleanup after containers stop")

    def collect(self, retained):
        try:
            candidates = self.client.images.list(filters={"label": [f"{CHECKPOINT_LABEL}=v1", f"{SCOPE_LABEL}={self.scope}"]})
            candidates.sort(key=lambda image: (len((image.attrs.get('RootFS') or {}).get('Layers', [])),
                                               image.attrs.get('Created', '')), reverse=True)
            self.release(image.id for image in candidates if image.id not in retained)
        except DockerException:
            logging.warning("System checkpoint cleanup unavailable; saved checkpoints retained")
