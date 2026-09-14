/**
 * TanStack Query hooks over the plain fetch functions in api.ts. Query
 * keys live here as the one source of truth so invalidation and cache
 * seeding (see useCreateResumeMutation) can't drift out of sync with
 * what a page actually queries by.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ResumeInput } from './types'
import {
  cloneResume,
  createResume,
  deleteResume,
  getDefaultResume,
  getResumeById,
  listResumes,
  setDefaultResume,
  updateResume,
} from './api'

export const queryKeys = {
  defaultResume: ['resumes', 'default'] as const,
  adminResumes: ['admin', 'resumes'] as const,
  adminResume: (id: number | 'new') => ['admin', 'resumes', id] as const,
}

export function useDefaultResumeQuery() {
  return useQuery({
    queryKey: queryKeys.defaultResume,
    queryFn: getDefaultResume,
  })
}

export function useAdminResumesQuery() {
  return useQuery({
    queryKey: queryKeys.adminResumes,
    queryFn: listResumes,
  })
}

export function useAdminResumeQuery(id: number | null) {
  return useQuery({
    queryKey: queryKeys.adminResume(id ?? 'new'),
    queryFn: () => getResumeById(id as number),
    enabled: id !== null,
  })
}

export function useCreateResumeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ResumeInput) => createResume(input),
    onSuccess: (resume) => {
      // Seeds the cache for the resume we just created so the redirect
      // to /admin/resumes/$id (see AdminResumeEditorPage) shows it
      // immediately instead of waiting on a redundant re-fetch.
      queryClient.setQueryData(queryKeys.adminResume(resume.id), resume)
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminResumes })
    },
  })
}

export function useUpdateResumeMutation(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ResumeInput) => updateResume(id, input),
    onSuccess: (resume) => {
      queryClient.setQueryData(queryKeys.adminResume(resume.id), resume)
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminResumes })
    },
  })
}

export function useDeleteResumeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteResume(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.adminResumes }),
  })
}

export function useCloneResumeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => cloneResume(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.adminResumes }),
  })
}

export function useSetDefaultResumeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => setDefaultResume(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminResumes })
      void queryClient.invalidateQueries({ queryKey: queryKeys.defaultResume })
    },
  })
}
