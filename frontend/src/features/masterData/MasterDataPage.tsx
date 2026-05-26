import { importEntityKeyByType } from './registry/masterDataEntities';
import { buildCsvSample, containsEncodingReplacementCharInRows } from './utils/formatters';
import { MasterDataLandingPage } from './MasterDataLandingPage';

export { buildCsvSample, containsEncodingReplacementCharInRows, importEntityKeyByType };

export function MasterDataPage() {
  return <MasterDataLandingPage />;
}
