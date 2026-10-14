// Where a Pokemon's artwork comes from: the local images/ folder when the app
// runs on this machine, the dataset's hosted artwork URL everywhere else
// (a deployed copy doesn't ship the ~125 MB images folder).
const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"];
const USE_LOCAL = LOCAL_HOSTS.includes(location.hostname);

export function imageSrc(p) {
  return USE_LOCAL || !p.image_url ? "/" + p.image_path : p.image_url;
}