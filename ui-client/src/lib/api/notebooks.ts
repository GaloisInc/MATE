import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";

export interface Notebook {
  content: string | null;
  created: string;
  format: null | "text" | "base64" | "json";
  last_modified: string;
  mimetype: string | null;
  name: string;
  path: string;
  size: number | null;
  type: string;
  writable: boolean;
}

export const getNotebook = async (path: string): Promise<Notebook | null> => {
  return axiosClient
    .get(`/api/v1/proxy/_notebook/api/contents/${path}`)
    .catch((e) => {
      if (e.response.status === 404) {
        return null;
      } else {
        return e;
      }
    })
    .then((resp) => {
      return resp ? resp.data : resp;
    });
};

export const createNotebook = async (
  path: string,
  buildId: string
): Promise<Notebook> => {
  return axiosClient
    .put(`/api/v1/proxy/_notebook/api/contents/${path}`, {
      type: "notebook",
      ext: "ipynb",
      content: {
        cells: [
          {
            cell_type: "code",
            execution_count: null,
            metadata: {},
            outputs: [],
            source: [
              "session = db.new_session()\n",
              `cpg = session.graph_from_build(session.query(db.Build).get("${buildId}"))\n`,
              "session.query(cpg.Node).count()",
            ],
          },
        ],
        metadata: {
          kernelspec: {
            display_name: "Python 3 (ipykernel)",
            language: "python",
            name: "python3",
          },
          language_info: {
            codemirror_mode: {
              name: "ipython",
              version: 3,
            },
            file_extension: ".py",
            mimetype: "text/x-python",
            name: "python",
            nbconvert_exporter: "python",
            pygments_lexer: "ipython3",
            version: "3.8.10",
          },
        },
        nbformat: 4,
        nbformat_minor: 4,
      },
    })
    .then(processResponse);
};
