#!/usr/bin/env python3
"""Script per aggiungere credentials: 'include' alle API calls"""

with open('frontend/src/api/client.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# Add credentials to getLibraryStats
old_stats = '''export async function getLibraryStats(): Promise<LibraryStats> {
  const response = await fetch(`${API_BASE}/library/stats`);'''

new_stats = '''export async function getLibraryStats(): Promise<LibraryStats> {
  const response = await fetch(`${API_BASE}/library/stats`, {
    credentials: 'include',
  });'''

content = content.replace(old_stats, new_stats)

# Add credentials to getAdvancedStats  
old_advanced = '''export async function getAdvancedStats(): Promise<AdvancedStats> {
  const response = await fetch(`${API_BASE}/library/stats/advanced`);'''

new_advanced = '''export async function getAdvancedStats(): Promise<AdvancedStats> {
  const response = await fetch(`${API_BASE}/library/stats/advanced`, {
    credentials: 'include',
  });'''

content = content.replace(old_advanced, new_advanced)

# Add credentials to deleteBook
old_delete = '''export async function deleteBook(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/library/${sessionId}`, {
    method: 'DELETE',
  });'''

new_delete = '''export async function deleteBook(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/library/${sessionId}`, {
    method: 'DELETE',
    credentials: 'include',
  });'''

content = content.replace(old_delete, new_delete)

with open('frontend/src/api/client.ts', 'w', encoding='utf-8') as f:
    f.write(content)

print('Modifiche applicate!')

# Verifica
if "credentials: 'include'," in content and 'getLibraryStats' in content:
    # Conta quante volte appare credentials: 'include' dopo la modifica
    count = content.count("credentials: 'include',")
    print(f'[OK] Trovate {count} occorrenze di credentials: include')
