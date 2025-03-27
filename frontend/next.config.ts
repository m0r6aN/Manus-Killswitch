import { NextConfig } from "next";
import path from "path";

const nextConfig = {
  webpack(config: NextConfig) {
    config.resolve.alias["@"] = path.join(__dirname, "src");
    return config;
  }
};

export default nextConfig;