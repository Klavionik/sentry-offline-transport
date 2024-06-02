# sentry-offline-transport
Transport for Sentry that saves failed-to-send events on disk and resends them on the next launch.

## Installation
`sentry-offline-trasport` requires Python >= 3.8.0, sentry-sdk >= 2.0.0.

Install from PyPI using `pip` or any other Python package manager.

`pip install sentry-offline-transport`

## Usage
To start using the transport, you have to provide a path to store failed events. It can be
an absolute or a relative path, either a string or a `Path` object. If the directory doesn't exist, 
it will be created along with all required parent directories.

By default, the transport will try to upload previously saved events right after the initialization.
You can configure this behavior using the `resend_on_startup` parameter.

```python
import sentry_sdk
from sentry_offline import make_offline_transport

sentry_sdk.init(
    dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234",
    transport=make_offline_transport(
        storage_path="~/.local/share/myapp/sentry_events", 
        resend_on_startup=False,
    ),
)
```
