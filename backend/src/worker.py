import logging
import time
from pathlib import Path
from src.services.execution import claim, execute, materialize_due
from src.services.settlement import claim_settlement, execute_settlement
from src.utils.wakeup import wait

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
heartbeat = Path('/tmp/analysis-heartbeat')


def main():
    while True:
        try:
            materialize_due()
            lease = claim()
            if lease:
                execute(lease)
            else:
                lease = claim_settlement()
                if lease:
                    execute_settlement(lease)
                else:
                    wait()
            heartbeat.touch()
        except Exception:
            log.exception('Worker cycle failed')
            time.sleep(2)


if __name__ == '__main__':
    main()
