import { useEffect, useState } from 'react';
import { listAdminSubjects, type SubjectRow } from './adminSubjectsApi';

export function AdminSubjectListPage() {
  const [subjects, setSubjects] = useState<SubjectRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSubjects() {
      const response = await listAdminSubjects();
      if (!response.success) {
        setError(response.error.message);
        setLoading(false);
        return;
      }

      setSubjects(response.data);
      setLoading(false);
    }

    void loadSubjects();
  }, []);

  return (
    <section className="card">
      <h2>Admin Subject List</h2>
      {loading ? <p className="muted">Loading subjects...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {!loading && !error ? (
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Credits</th>
            </tr>
          </thead>
          <tbody>
            {subjects.map((subject) => (
              <tr key={subject.subject_id}>
                <td>{subject.subject_code}</td>
                <td>{subject.subject_name}</td>
                <td>{subject.credits ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
