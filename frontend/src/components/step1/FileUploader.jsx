import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDropzone } from 'react-dropzone';

const FileUploader = ({ onUpload, loading }) => {
  const { t } = useTranslation();
  const [uploadProgress, setUploadProgress] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setUploadProgress(file.name);

    try {
      await onUpload(file);
      setUploadProgress(null);
    } catch (error) {
      setUploadProgress(null);
      alert(`Upload failed: ${error.message}`);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt']
    },
    maxSize: 10 * 1024 * 1024, // 10MB
    multiple: false,
    disabled: loading || uploadProgress
  });

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        {t('step1.fileUpload.title')}
      </h3>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        } ${(loading || uploadProgress) ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />

        {uploadProgress ? (
          <div className="flex flex-col items-center">
            <svg className="w-12 h-12 text-blue-600 animate-spin mb-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p className="text-gray-700">{t('step1.fileUpload.uploading')} {uploadProgress}...</p>
          </div>
        ) : (
          <>
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-4"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
              aria-hidden="true"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {isDragActive ? (
              <p className="text-blue-600 font-medium">{t('step1.fileUpload.dropHere')}</p>
            ) : (
              <>
                <p className="text-gray-700 mb-2">
                  {t('step1.fileUpload.dragDrop')}
                </p>
                <p className="text-sm text-gray-500">
                  {t('step1.fileUpload.supportedFormats')}
                </p>
              </>
            )}
          </>
        )}
      </div>

      {fileRejections.length > 0 && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-700 font-medium">{t('step1.fileUpload.rejected')}</p>
          <ul className="mt-1 text-sm text-red-600 list-disc list-inside">
            {fileRejections.map(({ file, errors }) => (
              <li key={file.name}>
                {file.name}: {errors.map(e => e.message).join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 text-xs text-gray-500">
        <p className="font-medium mb-1">{t('step1.fileUpload.supportedTypes')}</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>{t('step1.fileUpload.typePdf')}</li>
          <li>{t('step1.fileUpload.typeWord')}</li>
          <li>{t('step1.fileUpload.typeText')}</li>
        </ul>
      </div>
    </div>
  );
};

export default FileUploader;
