// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract SecurityScore {
    struct ScoreRecord {
        uint8 score;
        bytes1 grade;
        uint256 timestamp;
        bytes32 domainHash;
    }

    mapping(bytes32 => ScoreRecord) private scoreByDomainHash;

    event ScoreCalculated(
        bytes32 indexed domainHash,
        uint8 score,
        bytes1 grade,
        uint256 timestamp
    );

    function calculateScore(
        string calldata domain,
        uint256 domainAgeDays,
        uint8 tlsVersion,
        bool hasCSP,
        bool hasHSTS,
        bool hasForms,
        bool isCloudflare,
        bool isWordPress
    ) external returns (uint8 score, bytes1 grade) {
        int256 runningScore = 50;

        if (domainAgeDays > 365 * 5) {
            runningScore += 20;
        } else if (domainAgeDays > 365) {
            runningScore += 10;
        } else {
            runningScore -= 10;
        }

        if (tlsVersion == 13) {
            runningScore += 15;
        } else if (tlsVersion == 12) {
            runningScore += 5;
        } else {
            runningScore -= 15;
        }

        if (hasHSTS) {
            runningScore += 5;
        }

        if (hasCSP) {
            runningScore += 5;
        }

        if (isCloudflare) {
            runningScore += 10;
        }

        if (isWordPress) {
            runningScore -= 5;
        }

        if (hasForms) {
            runningScore -= 5;
        }

        if (runningScore < 0) {
            runningScore = 0;
        }

        if (runningScore > 100) {
            runningScore = 100;
        }

        uint8 finalScore = uint8(uint256(runningScore));
        bytes1 finalGrade = _gradeForScore(finalScore);
        bytes32 domainHash = keccak256(bytes(domain));

        scoreByDomainHash[domainHash] = ScoreRecord({
            score: finalScore,
            grade: finalGrade,
            timestamp: block.timestamp,
            domainHash: domainHash
        });

        emit ScoreCalculated(domainHash, finalScore, finalGrade, block.timestamp);

        return (finalScore, finalGrade);
    }

    function getLatestScore(string calldata domain)
        external
        view
        returns (
            uint8 score,
            bytes1 grade,
            uint256 timestamp,
            bytes32 domainHash
        )
    {
        bytes32 hashedDomain = keccak256(bytes(domain));
        ScoreRecord memory record = scoreByDomainHash[hashedDomain];
        return (record.score, record.grade, record.timestamp, record.domainHash);
    }

    function getScoreByHash(bytes32 domainHash)
        external
        view
        returns (uint8 score, bytes1 grade, uint256 timestamp)
    {
        ScoreRecord memory record = scoreByDomainHash[domainHash];
        return (record.score, record.grade, record.timestamp);
    }

    function _gradeForScore(uint8 score) private pure returns (bytes1) {
        if (score >= 85) {
            return bytes1("A");
        }

        if (score >= 70) {
            return bytes1("B");
        }

        if (score >= 55) {
            return bytes1("C");
        }

        return bytes1("D");
    }
}
