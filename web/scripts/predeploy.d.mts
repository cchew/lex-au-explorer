export declare function resolvePredeploy(
  env: Record<string, string | undefined>,
  exists: (path: string) => boolean,
): {
  ok: boolean;
  errors: string[];
  corpusDir?: string;
  graphJson?: string;
  imagesDir?: string;
};
