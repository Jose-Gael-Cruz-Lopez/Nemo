# Local persistence adapters

Implement SQLite as the durable local fallback and JSON only for lightweight append-only/replay use. Keep the persistence interface shared with the optional Butterbase adapter so local operation does not depend on a network service.
