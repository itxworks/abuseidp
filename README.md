# abuseidp
AbuseIPDB - Selfhosted Blacklist
### Docker Compose
```
---
services:
  app:
    container_name: abusedb
    image: mp0185/abuseidp:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config      # Synchronize the local config directory with the container
      - ./logs:/app/logs          # Synchronize the local logs directory with the container
    restart: always
```

### config.ini
```
[API]
api_key = 3829b228e4b30f391cadf5225a0178fe6173c339edd117d0cf071e720373a8d45bfe7a2981350174
download_interval_hours = 3
confidence_minimum = 75
[Server]
port = 8000
[Settings]
update_interval = 24
expiration_period = 30
whitelist =
```