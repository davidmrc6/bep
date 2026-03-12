"""
TODO: Filtering approach
1. for each candidate repo, filter out repos with:
    - low number of pull requests (e.g., under 3-5) + self-merged prs, prs with no comments
2, pull all review-related text (PR review comments, PR general comments (maybe issues if the dataset is too scarce)
3. run every extracted comment through a language detection model (e.g. lid.176.bin) with a confidence
   threshold of 0.7, and manually review borderline cases (between 0.5 and 0.7)
4. take a random sample of the filtered comments and manually verify that they're actually romanian
   and express some sort of sentiment relevant to code review
"""