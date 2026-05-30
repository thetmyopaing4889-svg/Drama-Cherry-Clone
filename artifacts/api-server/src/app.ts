import express, { type Express, type Request, type Response, type NextFunction } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import path from "path";
import router from "./routes";
import { logger } from "./lib/logger";

const PIPELINE_DIR = process.env["PIPELINE_DIR"] ?? path.join(__dirname, "../../../pipeline");

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use("/api/outputs", express.static(path.join(PIPELINE_DIR, "outputs")));

app.use("/api", router);

app.use((err: unknown, req: Request, res: Response, _next: NextFunction) => {
  const status = (err as { status?: number; statusCode?: number }).status
    ?? (err as { status?: number; statusCode?: number }).statusCode
    ?? 500;
  const message = err instanceof Error ? err.message : "Internal server error";
  logger.error({ err, url: req.url, method: req.method }, "Unhandled error");
  res.status(status).json({ error: message });
});

export default app;
