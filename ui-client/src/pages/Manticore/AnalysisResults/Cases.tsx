export interface AnalysisResultCase {
  description: string;
  condition: string;
  constraints: string[];
  va: number;
  va_mapping?: string;
}

interface CasesProps {
  cases: AnalysisResultCase[];
  stateId: number;
}

export const Cases = ({ cases, stateId }: CasesProps) => {
  return (
    <>
      Potential Bugs:
      {cases.length > 0 ? (
        <ul>
          {cases.map((c) => (
            <li key={c.va}>
              <h5>{c.description} at <code>0x{c.va.toString(16)}</code> (<code>{c.va_mapping ?? "unknown mapping"}</code>)</h5>
              <p>
                Under the condition: <code>{c.condition}</code>
              </p>

              <p>
                With the following constraints:

                <ul>
                  {c.constraints.map((s) => (
                    <li key={s}>
                      <code>{s}</code>
                    </li>
                  ))}
                </ul>
              </p>

            </li>
          ))}
        </ul>
      ) : (
        <> No potential bugs found in state {stateId}</>
      )}
    </>
  );
};
