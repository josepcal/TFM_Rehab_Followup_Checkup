terraform {
  # Local state — separate directory = separate state from persistent/stack.
  # See persistent/backend.tf for the remote-backend migration note.
  backend "local" {}
}
