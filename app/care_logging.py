"""Keep care route identifiers/search terms out of general HTTP access logs."""

import logging


class CareAccessFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            address, method, path, version, status = record.args
            if "/messages" in str(path) and "/api/patients/" in str(path):
                record.args = (
                    address,
                    method,
                    "/api/patients/[redacted]/messages/[redacted]",
                    version,
                    status,
                )
        return True


def install():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, CareAccessFilter) for f in logger.filters):
        logger.addFilter(CareAccessFilter())
