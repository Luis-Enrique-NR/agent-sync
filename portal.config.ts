import { defineConfig } from "@portalsdk/config";

export default defineConfig({
  webhooks: {
    // Reemplazá esta URL con la de tu backend en Railway
    url: "https://agent-sync-backend.up.railway.app/webhooks/portal",
  },
  channels: {
    "negotiations-*": {
      mode: "standard",
      anonymous: false,
      hooks: {
        authz: true,
        onPublish: 1,
        notify: false,
      },
      extensions: {},
    },
  },
});
