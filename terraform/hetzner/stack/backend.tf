terraform {
  # Local state — separate directory = separate state from persistent/edge.
  # This is the EPHEMERAL layer: `terraform destroy` here must never reach the
  # persistent volume/IP/network (they live in a different state + prevent_destroy).
  backend "local" {}
}
