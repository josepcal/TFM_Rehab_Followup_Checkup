# Read-only reference to the persistent layer. Cannot mutate/destroy its resources.
data "terraform_remote_state" "persistent" {
  backend = "local"

  config = {
    path = var.persistent_state_path
  }
}

locals {
  network_id          = data.terraform_remote_state.persistent.outputs.network_id
  volume_id           = data.terraform_remote_state.persistent.outputs.volume_id
  volume_linux_device = data.terraform_remote_state.persistent.outputs.volume_linux_device
  location            = data.terraform_remote_state.persistent.outputs.location
}
