# sentry-offline-transport
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/Klavionik/sentry-offline-transport/graph/badge.svg?token=L5GROOX2QN)](https://codecov.io/gh/Klavionik/sentry-offline-transport)
[![PyPI - Version](https://img.shields.io/pypi/v/sentry-offline-transport)](https://pypi.org/project/sentry-offline-transport)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/sentry-offline-transport)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/sentry-offline-transport)](https://pypistats.org/packages/sentry-offline-transport)

Transport for Sentry that saves failed-to-send events and resends them on the next launch.

## Installation
`sentry-offline-trasport` requires Python >= 3.8.0, sentry-sdk >= 2.0.0.

Install from PyPI using `pip` or any other Python package manager.

`pip install sentry-offline-transport`

## Usage
To start using the transport, you have to provide a path to store failed events. It can be
an absolute or a relative path, either a string or a `Path` object. If the directory doesn't exist, 
it will be created along with all required parent directories.

By default, the transport will try to upload previously saved events right after the initialization.
You can configure this behavior using the `reupload_on_startup` parameter.

```python
import sentry_sdk
from sentry_offline import make_offline_transport

sentry_sdk.init(
    dsn="https://asdf@abcd1234.ingest.us.sentry.io/1234",
    transport=make_offline_transport(
        storage_path="~/.local/share/myapp/sentry_events", 
        reupload_on_startup=False,
    ),
)
```
