export async function loadPublicDirectory() {
  return fetch('/api/directory/staff').then((response) => response.json());
}

export async function loadCoordinatorAssignment(staffId) {
  return fetch(`/api/directory/staff/${staffId}/assignment`).then((response) => response.json());
}
