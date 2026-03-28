library(caret) 

dataset <- read.csv("datasets/novielli-gh-gold/github_gold.csv", header=TRUE, sep=";")

set.seed(846)
splitIndex <- createDataPartition(dataset$Polarity, p = .70, list = FALSE)
testIndices <- setdiff(1:nrow(dataset), splitIndex)

write.csv(dataset$ID[testIndices], "output/novielli_test_ids.csv", row.names=FALSE)
