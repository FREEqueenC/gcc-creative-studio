resource "openfga_store" "creative_studio_store" {
  name = "creative-studio-store"
}

resource "openfga_authorization_model" "creative_studio_model" {
  store_id       = openfga_store.creative_studio_store.id
  schema_version = "1.1"
  dsl            = <<EOT
model
  schema 1.1

type user

type group
  relations
    define member: [user]

type workspace
  relations
    define owner: [user, group#member]
    define editor: [user, group#member] or owner
    define viewer: [user, group#member, user:*] or editor

type asset
  relations
    define parent: [workspace]
    define can_view: viewer from parent
    define can_edit: editor from parent
EOT
}
