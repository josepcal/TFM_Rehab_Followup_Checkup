# Read-only reference to the persistent layer. Cannot mutate/destroy its resources.
data "terraform_remote_state" "persistent" {
  backend = "local"

  config = {
    path = var.persistent_state_path
  }
}

locals {
  network_id          = data.terraform_remote_state.persistent.outputs.network_id
  floating_ip_id      = data.terraform_remote_state.persistent.outputs.floating_ip_id
  floating_ip_address = data.terraform_remote_state.persistent.outputs.floating_ip_address
  location            = data.terraform_remote_state.persistent.outputs.location
  subnet_ip_range     = data.terraform_remote_state.persistent.outputs.subnet_ip_range
}
