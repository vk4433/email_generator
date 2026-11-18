import { Container, getContainer } from "@cloudflare/containers";

export class McpServerContainer extends Container {
    defaultPort = 8000;
    sleepAfter = "10m";
    envVars = {
          SUPABASE_URL: this.env.SUPABASE_URL,
          SUPABASE_KEY: this.env.SUPABASE_KEY,
          DATABASE_URL: this.env.DATABASE_URL,
          GEMINI_API_KEY: this.env.GEMINI_API_KEY,
          DEEPSEEK_API_KEY: this.env.DEEPSEEK_API_KEY,
    };
}

export default {
    async fetch(request: Request, env: Env) {
          const container = getContainer(env.MCP_SERVER);
          return container.fetch(request);
    },
};
